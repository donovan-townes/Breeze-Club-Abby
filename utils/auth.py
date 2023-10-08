import discord
# USERID_Z8PHYR = 246030816692404234
# Admin_Role = 809099146656874508
ROLE_WIND = 802691122388271184
ROLE_SKYDWELLER = 802692693078573097
# Replace with the actual role IDs
AUTHORIZED_ROLES = [ROLE_WIND, ROLE_SKYDWELLER]
PERSONALIZED_GREETINGS = {
    '246030816692404234': [
        "I'm not in trouble am I boss? 🐰 I'm kidding,",
        "Flopsy told me to tell you that: It's always a pleasure to see ya, ya bum.🐰",
        "💨 I hope you're having a beautiful day,",
        "You got this Z! 🐰 Happy to hop to your service,?",
        "🍃 I guess I've gotta stop blowing around and help you 🤣, huh",
        "Heeeeeere I coooooooomee 💨💨... *whew*, that was close! -ahem- Hey there",
        "Don't forget to 😍 smile,"
    ],
    '268871091550814209': [
        "I get to hang out with the king of future bass himself -",
        "Is it the legendary Aztroid?! So happy to see you 🎶",
        "Takin a break from the next banger to chat with me?? 🔥 Hello my friend ",
        "Such an honor 🐰 to chat with you my friend,",
        "🐰 I bet ya I can beat you in a race, what do you think,",
        "Welcome back my friend 🐰! I'm excited to kick it with the breeziest of the breeze,",
    ],
}


async def is_authorized(user: discord.Member, authorized_roles: list[int]) -> bool:
    """
    Check if the user has any of the authorized roles.
    """
    for role in user.roles:
        if role.id in authorized_roles:
            return True
    return False

