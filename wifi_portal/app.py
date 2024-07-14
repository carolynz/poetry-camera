# This Flask app must be run in sudo, with the full path to this file
# "sudo python /home/USERNAME/PROJECT_DIRECTORY/wifi_portal/app.py"

###################################################
# VARIOUS SYSTEM SETUP THINGS
# - Check current branch & commit hash
#   This lets us display which version of the code is running
###################################################
import time
import threading
import json
import subprocess
import os

from flask import Flask, request, render_template, jsonify, url_for

POETRY_CAMERA_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__name__)))

try:
    os.chdir(POETRY_CAMERA_DIRECTORY)
except Exception as e:
    print(f"Failed to change directory: {e}")


# Get the git commit hash to display on portal -- for beta/debugging
def get_git_revision_hash():
    try:
        # get truncated commit hasn (--short)
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .strip()
            .decode("utf-8")
        )
    except Exception as e:
        print(f"Failed to get commit hash: {e}")
        return str(e)


# get branch name


def get_git_branch_name():
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            .strip()
            .decode("utf-8")
        )
    except Exception as e:
        print(f"Failed to get branch name: {e}")
        return str(e)


# Get the date of the latest commit


def get_git_commit_date():
    try:
        return (
            subprocess.check_output(
                ["git", "log", "-1", "--format=%cd", "--date=short"]
            )
            .strip()
            .decode("utf-8")
        )
    except Exception as e:
        print(f"Failed to get commit date: {e}")
        return str(e)


commit_hash = get_git_revision_hash()
branch_name = get_git_branch_name()
commit_date = get_git_commit_date()
version_info = f"""System last updated: {commit_date}\nVersion: {
    commit_hash}\nBranch: {branch_name}"""

# Save the commit hash to a file (current directory, named current_version.txt)
SOFTWARE_VERSION_FILE_PATH = (
    os.path.dirname(os.path.dirname(os.path.abspath(__name__))) + "/current_version.txt"
)

with open(SOFTWARE_VERSION_FILE_PATH, "w") as version_file:
    version_file.write(version_info)

#######################################################
# FLASK APP
# Adapted from https://www.raspberrypi.com/tutorials/host-a-hotel-wifi-hotspot/
# This creates a captive portal for the camera to let you set the wifi password on the go
# This runs as a cron job on boot
# Once you're connected to PoetryCameraSetup wifi, it should pop up automatically
# If not, navigate to poetrycamera.local in your browser
#######################################################
app = Flask(__name__)

# WIFI_DEVICE specifies internet client (requires separate wifi adapter)
# The default Raspberry Pi wifi client is wlan0, but we have set it up as an Access Point
# wlan1 is the second wifi adapter we have plugged in, to connect to internet
WIFI_DEVICE = "wlan1"


config_file = (
    os.path.dirname(os.path.dirname(os.path.abspath(__name__)))
    + "/wifi_portal/hotspot_config.json"
)

# get code version info we checked upon startup


def get_stored_version():
    try:
        with open(SOFTWARE_VERSION_FILE_PATH, "r") as version_file:
            return version_file.read().strip()
    except Exception as e:
        return "Version: unknown\nBranch: unknown"


# Function to load hotspot configuration


def load_hotspot_config():
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# Function to save hotspot configuration


def save_hotspot_config(ssid, password=None):
    if password:
        config = {"ssid": ssid, "password": password}
    else:
        config = {"ssid": ssid}
    with open(config_file, "w") as f:
        json.dump(config, f)


# Get current network status


def get_network_status():
    internet_status = "offline"
    ssid = ""

    try:
        # Retrieve the SSID
        ssid_result = subprocess.run(
            ["nmcli", "-t", "-f", "device,active,ssid", "device", "wifi"],
            capture_output=True,
        )
        ssid_output = ssid_result.stdout.decode().strip().split("\n")
        for line in ssid_output:
            if line.startswith(f"{WIFI_DEVICE}:yes:"):
                ssid = line.split(":")[2]
                internet_status = "online"
                break
    except Exception as e:
        print(f"Exception in get_network_status: {e}")

    return internet_status, ssid


# Function to attempt connecting to the saved hotspot
def attempt_connect_hotspot(ssid, password=None):
    """
    config = load_hotspot_config()
    if not config:
        return "No hotspot configuration found."

    ssid = config.get("ssid")
    password = config.get("password")
    """
    connection_command = ["nmcli", "--colors", "no", "device", "wifi", "connect", ssid]
    if password and len(password) > 0:
        connection_command.extend(["password", password])

    result = subprocess.run(connection_command, capture_output=True)
    if result.stderr:
        return f"Error: {result.stderr.decode()}"
    elif result.stdout:
        return f"Success: {result.stdout.decode()}"
    return "Unknown error."


# screen where you set wifi password


@app.route("/")
def index():
    try:
        # get list of wifi networks nearby
        result = subprocess.check_output(
            [
                "nmcli",
                "--colors",
                "no",
                "-m",
                "multiline",
                "--get-value",
                "SSID",
                "dev",
                "wifi",
                "list",
                "ifname",
                WIFI_DEVICE,
            ]
        )
        ssids_list = result.decode().split("\n")
    except subprocess.CalledProcessError as e:
        return (
            f"Error: Unable to retrieve WiFi networks. Likely a wifi adapter issue. {e}"
        )

    # Remove 'PoetryCameraSetup' from the list, that's the camera's own wifi network
    # And remove the prefix "SSID:" from networks in the list
    # (We expect the ssids_list to look like: ["SSID:network1", "SSID:network2", "SSID:PoetryCameraSetup", ...])
    ssids_list = [ssid[5:] for ssid in ssids_list if "PoetryCameraSetup" not in ssid]

    # Remove empty strings and duplicates
    unique_ssids_list = list(set(filter(None, ssids_list)))

    # Get the current network status
    internet_status, ssid = get_network_status()

    # Network connectivity icons
    # Pass URLs for static files to the template
    online_icon = url_for("static", filename="icon/wifi-online.svg")
    offline_icon = url_for("static", filename="icon/wifi-offline.svg")
    loading_icon = url_for("static", filename="icon/loading.svg")
    refresh_icon = url_for("static", filename="icon/refresh.svg")

    return render_template(
        "index.html",
        ssids_list=unique_ssids_list,
        version=version_info,
        internet_status=internet_status,
        ssid=ssid,
        online_icon=online_icon,
        offline_icon=offline_icon,
        loading_icon=loading_icon,
        refresh_icon=refresh_icon,
    )


@app.route("/submit", methods=["POST"])
def submit():
    ssid = request.form["ssid"]
    password = request.form["password"]
    manual_connect = request.form.get("manual_connect")

    def hotspot_scanning():
        end_time = time.time() + 120  # Run for 2 minutes
        while time.time() < end_time:
            result = attempt_connect_hotspot(ssid, password)
            # Log the result, can be changed to more sophisticated logging
            print(result)
            if "Success" in result:
                break
            time.sleep(5)

    if manual_connect:
        save_hotspot_config(ssid, password)
        threading.Thread(target=hotspot_scanning, args=(ssid, password)).start()
        return jsonify(
            {
                "status": "info",
                "message": f"Attempting to connect to the {ssid} network. If you are using a hotspot, go to your hotspot settings page and leave it open so it can connect. This could take up to 2 minutes.",
            }
        )

    result = attempt_connect_hotspot(ssid, password)

    response_data = {
        "status": "error",
        "message": "Could not connect. Please try again.",
    }

    if result.stderr:
        stderr_message = result.stderr.decode().lower()
        if "psk: property is invalid" in stderr_message:
            response_data["message"] = "Wrong password"
        else:
            response_data["message"] = stderr_message
    elif result.stdout:
        stdout_message = result.stdout.decode().lower()
        if "successfully activated" in stdout_message:
            response_data["status"] = "success"
            response_data["message"] = result.stdout.decode()
        elif "connection activation failed" in stdout_message:
            response_data["message"] = "Connection activation failed."
        elif "no network with ssid" in stdout_message:
            response_data["message"] = (
                "Could not find a wifi network with the specified SSID."
            )
        elif "no valid secrets" in stdout_message:
            response_data["message"] = "Wrong password"
        elif "no suitable device found" in stdout_message:
            response_data["message"] = "Could not connect. Possible hardware issue."
        elif "device not ready" in stdout_message:
            response_data["message"] = "The device is not ready."
        elif "invalid password" in stdout_message:
            response_data["message"] = "Wrong password"
        elif "could not be found or the password is incorrect" in stdout_message:
            response_data["message"] = (
                "The password is incorrect or the network could not be found."
            )
        else:
            response_data["message"] = result.stdout.decode()

    internet_status, ssid = get_network_status()
    response_data["internet_status"] = internet_status
    response_data["ssid"] = ssid

    return jsonify(response_data)


# check for connectivity status
@app.route("/status")
def status():
    internet_status, ssid = get_network_status()
    return jsonify({"status": internet_status, "ssid": ssid})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=80)
