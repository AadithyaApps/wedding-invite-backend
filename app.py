from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os, git
from datetime import datetime
from datetime import datetime, timezone
from git import Repo
import shutil
from google.cloud import firestore
import pytz
import json
import tempfile

credentials_path = '/tmp/gcp-creds.json'
creds_content = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')

if creds_content:
    with open(credentials_path, 'w') as f:
        f.write(creds_content)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    
    
    
    
app = Flask(__name__)
CORS(app)

@app.route("/publish", methods=["POST"])
def publish():
    try:
        data = request.get_json()
        print("Received Data:", data)

        required_fields = ['groomName', 'brideName', 'eventType', 'venueAddress', 'venueName', 
                           'brideFather', 'brideMother', 'groomFather', 'groomMother']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400

        groom = data['groomName'].replace(' ', '')
        bride = data['brideName'].replace(' ', '')
        file_name = f"{groom}And{bride}.html"

        # Render HTML safely
        rendered_html = render_template("public_template.html", **data)

        local_file_path = os.path.join("/tmp", file_name)
        with open(local_file_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
        print(f"HTML file generated at {local_file_path}")

        # GitHub Setup
        git_username = os.environ['GIT_USERNAME']
        git_token = os.environ['GIT_TOKEN']

        if not git_username or not git_token:
            return jsonify({"error": "Git credentials missing in environment"}), 500

        repo_url = f"https://{git_username}:{git_token}@github.com/AadithyaApps/wedding-invite-public.git"
        repo_dir = "/tmp/wedding-invite-public"

        if not os.path.exists(repo_dir):
            print("Cloning repo...")
            git.Repo.clone_from(repo_url, repo_dir)
        repo = git.Repo(repo_dir)

        invites_folder = os.path.join(repo_dir, 'public-invites')
        os.makedirs(invites_folder, exist_ok=True)
        final_file_path = os.path.join(invites_folder, file_name)
        os.replace(local_file_path, final_file_path)
        print(f"Moved invite to {final_file_path}")

        # Git Config
        repo.git.config('user.email', 'aadithya.ofc@gmail.com')
        repo.git.config('user.name', 'Aadithya Sridharan')

        repo.git.add(all=True)
        print("Files in public-invites folder:", os.listdir(invites_folder))
        print("Full path file exists?", os.path.isfile(final_file_path))
        status = repo.git.status()
        print("Git status:", status)

        repo.git.commit('-m', f"Added invite for {groom} and {bride}")
        repo.git.push()
        print("Git push successful!")

        netlify_url = f"https://invitemaker.netlify.app/public-invites/{file_name}"

        return jsonify({"message": "Invite published!", "url": netlify_url})

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500



@app.route("/cleanup", methods=["GET"])
def cleanup():
    try:
        print("Cleanup started...")

        # Firebase credentials should be set via GOOGLE_APPLICATION_CREDENTIALS
        db = firestore.Client()

        git_username = os.environ.get('GIT_USERNAME')
        git_token = os.environ.get('GIT_TOKEN')

        if not git_username or not git_token:
            return jsonify({"error": "Git credentials missing in environment"}), 500

        repo_url = f"https://{git_username}:{git_token}@github.com/AadithyaApps/wedding-invite-public.git"
        repo_dir = "/tmp/wedding-invite-public"

        if not os.path.exists(repo_dir):
            git.Repo.clone_from(repo_url, repo_dir)
        repo = git.Repo(repo_dir)
        repo.git.config('user.email', 'aadithya.ofc@gmail.com')
        repo.git.config('user.name', 'Aadithya Sridharan')
        repo.remotes.origin.pull()

        invites_folder = os.path.join(repo_dir, 'public-invites')
        temp_folder = os.path.join(invites_folder, 'temp_invites')
        os.makedirs(temp_folder, exist_ok=True)

        all_links = db.collection("published_links").stream()

        moved_files = []
        now = datetime.now(timezone.utc)

        for link in all_links:
            link_data = link.to_dict()
            invite_url = link_data.get('inviteUrl')
            expires_at = link_data.get('expiresAt')

            if not invite_url or not expires_at:
                continue

            file_name = invite_url.strip().split('/')[-1]
            file_path = os.path.join(invites_folder, file_name)

            if not os.path.isfile(file_path):
                print(f"File {file_name} not found in public-invites, skipping.")
                continue

            expires_dt = expires_at.replace(tzinfo=timezone.utc)

            if now > expires_dt:
                print(f"{file_name} expired, moving to temp_invites.")
                shutil.move(file_path, os.path.join(temp_folder, file_name))
                moved_files.append(file_name)
            else:
                print(f"{file_name} is still valid till {expires_dt}.")

        if moved_files:
            repo.git.add(all=True)
            repo.git.commit('-m', f"Moved {len(moved_files)} expired invites to temp_invites")
            repo.git.push()

        return jsonify({
            "status": "Cleanup completed",
            "moved_files": moved_files
        }), 200

    except Exception as e:
        print("Cleanup Error:", str(e))
        return jsonify({"error": str(e)}), 500
        

@app.route("/restore-invite", methods=["POST"])
def restore_invite():
    try:
        data = request.get_json()
        invite_url = data.get('inviteUrl')

        if not invite_url:
            return jsonify({"error": "No inviteUrl provided"}), 400

        filename = invite_url.strip().split('/')[-1]

        print(f"Restoring invite: {filename}")

        git_username = os.environ.get('GIT_USERNAME')
        git_token = os.environ.get('GIT_TOKEN')

        if not git_username or not git_token:
            return jsonify({"error": "Git credentials missing in environment"}), 500

        repo_url = f"https://{git_username}:{git_token}@github.com/AadithyaApps/wedding-invite-public.git"
        repo_dir = "/tmp/wedding-invite-public"

        if not os.path.exists(repo_dir):
            print("Cloning repo...")
            git.Repo.clone_from(repo_url, repo_dir)
        repo = git.Repo(repo_dir)

        invites_folder = os.path.join(repo_dir, 'public-invites')
        temp_folder = os.path.join(invites_folder, 'temp_invites')

        active_file_path = os.path.join(invites_folder, filename)
        temp_file_path = os.path.join(temp_folder, filename)

        repo.git.config('user.email', 'aadithya.ofc@gmail.com')
        repo.git.config('user.name', 'Aadithya Sridharan')
        repo.remotes.origin.pull()

        if os.path.exists(active_file_path):
            print(f"{filename} already exists in public-invites")
            return jsonify({"status": "exists", "message": "File already active"}), 200

        if os.path.exists(temp_file_path):
            print(f"Restoring {filename} from temp_invites")
            shutil.move(temp_file_path, active_file_path)
            repo.git.add(all=True)
            repo.git.commit('-m', f"Restored invite {filename} after payment success")
            repo.git.push()
            print("Restoration pushed to GitHub")
            return jsonify({"status": "restored", "message": f"{filename} restored"}), 200

        print(f"{filename} not found in temp_invites or public-invites")
        return jsonify({"status": "not_found", "message": f"{filename} not found"}), 404

    except Exception as e:
        print("Restore Error:", str(e))
        return jsonify({"error": str(e), "message": "An error occurred during restoration"}), 500


if __name__ == "__main__":
    app.run(debug=True)
