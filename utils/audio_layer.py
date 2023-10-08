import os
import subprocess
import shutil
def get_most_recent_folder(path):
    # List all directories in the given path
    dirs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]

    # Find the most recent folder based on the creation time (ctime)
    most_recent_folder = max(dirs, key=lambda d: os.path.getctime(os.path.join(path, d)))

    return os.path.join(path, most_recent_folder)

def layer_wav_files(output_path, input_dir):
    # Get all the wav files in the input directory
    input_files = [os.path.join(input_dir, file) for file in os.listdir(input_dir) if file.lower().endswith(".wav")]

        # If there's only one input file, directly copy it to the output path
    if len(input_files) == 1:
        shutil.copyfile(input_files[0], output_path)
        return
    # Build the ffmpeg command
    ffmpeg_cmd = [
        "ffmpeg",
        *sum([["-i", file] for file in input_files], []),  # Flatten the list of input file options
        "-filter_complex",
        "[0:a][1:a]amix=inputs={}:duration=first:dropout_transition=2".format(len(input_files)),
        "-c:a",
        "pcm_s16le",
        output_path
    ]

    # Run the ffmpeg command
    subprocess.run(ffmpeg_cmd)

if __name__ == "__main__":
    # Replace this path with the actual parent folder containing the audio recording folders
    input_dir = "/home/Abby_BreezeClub/Audio_Recordings"

    # Replace this path with the desired output path
    output_path = "/home/Abby_BreezeClub/Audio_Recordings/OUTPUT.wav"

    layer_wav_files(output_path, input_dir)

    