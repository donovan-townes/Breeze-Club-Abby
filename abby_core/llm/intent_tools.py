"""Execute intent-based tools (guild info, bot status, etc.).

Bridges IntentAction requests to actual platform operations via tool factory.

Architecture:
    IntentAction (LLM output)
            ↓
    execute_tool (this module) - delegates to tool factory
            ↓
    ToolFactory.get_tool(platform, tool_type)
            ↓
    Platform-specific tool (Discord, Web, CLI, etc.)

This module is platform-agnostic: it doesn't import or know about specific
platforms (Discord, Web, etc.). Instead, it uses the ToolFactory registry
that adapters populate during startup.

Platform adapters register their tool implementations:
    factory = get_tool_factory()
    factory.register("discord", "guild_info", DiscordGuildInfoTool())
    factory.register("web", "guild_info", WebGuildInfoTool())

Then intent_tools looks up the right tool at runtime:
    tool = factory.get_tool("discord", "guild_info")
    result = await tool.execute(args)
"""

from typing import Dict, Any, Optional
import logging

from abby_core.interfaces.tools import get_tool_factory, ToolResult

logger = logging.getLogger(__name__)


async def execute_tool(
    action: Any,
    platform: str = "discord",
    bot: Optional[Any] = None
) -> Dict[str, Any]:
    """Execute a tool based on IntentAction using the tool factory.
    
    Looks up the tool implementation via factory (platform-agnostic approach),
    executes it with the provided arguments, and returns results as a dict.
    
    Flow:
        1. Get tool from factory registry
        2. Execute tool with action arguments
        3. Return normalized result as dict
    
    Args:
        action: IntentAction with tool_name and tool_args
        platform: Platform identifier ("discord", "web", "cli", etc.)
        bot: Optional platform client (context for tool execution)
        
    Returns:
        Dictionary with 'text' (str) and optional 'embed' (platform type)
    
    Example:
        # In Discord cog
        result = await execute_tool(intent_action, platform="discord", bot=bot)
        await ctx.send(result["text"], embed=result.get("embed"))
    """
    if not action.use_llm and action.action_type == "tool":
        tool_name = action.tool_name
        tool_args = action.tool_args or {}
        
        logger.info(f"[execute_tool] Running tool: {tool_name} (platform: {platform})")
        
        try:
            # Get tool from factory (platform-independent lookup)
            factory = get_tool_factory()
            tool = factory.get_tool(platform, tool_name)
            
            if not tool:
                logger.warning(f"[execute_tool] Tool '{tool_name}' not registered for platform '{platform}'")
                return {
                    "text": f"Tool '{tool_name}' is not available on this platform",
                    "error": f"Tool not found: {tool_name}/{platform}"
                }
            
            # Build tool context (includes bot instance and other data)
            context = {
                "bot": bot,
                "platform": platform,
                **tool_args
            }
            
            # Execute tool (returns ToolResult with normalized data)
            result = await tool.execute(context)
            
            # Convert ToolResult or dict to response dict with text
            if isinstance(result, ToolResult):
                result_dict = result.to_dict()
                return _normalize_tool_result(result_dict)
            if hasattr(result, "to_dict"):
                result_dict = result.to_dict()
                if isinstance(result_dict, dict):
                    return _normalize_tool_result(result_dict)
            if isinstance(result, dict):
                return _normalize_tool_result(result)
            # Fallback for non-standard result types
            return {"text": str(result)}
        
        except Exception as e:
            logger.error(f"[execute_tool] Error executing {tool_name}: {e}", exc_info=True)
            return {
                "text": f"Error executing tool: {str(e)}",
                "error": str(e)
            }
    
    # For non-tool actions (refusal, stub, etc.), return pre-computed text
    if hasattr(action, 'text') and action.text:
        return {"text": action.text}
    
    return {"text": "No response available."}


def _normalize_tool_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure tool results include a text field for callers."""
    if "text" in result:
        return result

    text = result.get("message") or result.get("error") or ""
    if not text and "data" in result:
        text = str(result.get("data"))

    normalized = {"text": text}
    normalized.update(result)
    return normalized

