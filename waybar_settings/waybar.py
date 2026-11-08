import subprocess

RELOAD_COMMAND = ["pkill", "-SIGUSR2", "waybar"]
START_COMMAND = ["waybar"]

def reload_waybar():
    result = subprocess.run(RELOAD_COMMAND)
    if result.returncode == 1:
        subprocess.Popen(START_COMMAND, start_new_session=True)
    