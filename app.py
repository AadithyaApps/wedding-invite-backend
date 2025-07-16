from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os, git
from datetime import datetime
from datetime import datetime, timezone
from git import Repo


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

        git_username = os.environ.get('GIT_USERNAME')
        git_token = os.environ.get('GIT_TOKEN')

        if not git_username or not git_token:
            print("Git credentials missing in environment.")
            return jsonify({"error": "Git credentials missing in environment"}), 500

        repo_url = f"https://{git_username}:{git_token}@github.com/AadithyaApps/wedding-invite-public.git"
        repo_dir = "/tmp/wedding-invite-public"

        if not os.path.exists(repo_dir):
            print("Cloning repository...")
            git.Repo.clone_from(repo_url, repo_dir)
        else:
            print("Repository already exists.")

        repo = git.Repo(repo_dir)
        repo.git.config('user.email', 'aadithya.ofc@gmail.com')
        repo.git.config('user.name', 'Aadithya Sridharan')

        print("Pulling latest changes...")
        repo.remotes.origin.pull()

        invites_folder = os.path.join(repo_dir, 'public-invites')
        temp_folder = os.path.join(invites_folder, 'temp_invites')
        os.makedirs(temp_folder, exist_ok=True)

        print(f"Scanning folder: {invites_folder}")
        print("Existing files:", os.listdir(invites_folder))

        from datetime import datetime

        moved_files = []

        for file in os.listdir(invites_folder):
            file_path = os.path.join(invites_folder, file)

            if file == 'temp_invites' or not file.endswith('.html'):
                print(f"Skipping {file}")
                continue

            try:
                commits = list(repo.iter_commits(paths=file_path, max_count=1))
                if not commits:
                    print(f"No commits found for {file}, skipping.")
                    continue

                last_commit_time = commits[0].committed_date
                age_seconds = datetime.utcnow().timestamp() - last_commit_time
                print(f"File: {file}, Last Commit Age (seconds): {age_seconds}")

                if age_seconds > 5 * 60:
                    new_path = os.path.join(temp_folder, file)
                    os.replace(file_path, new_path)
                    moved_files.append(file)
                    print(f"Moved {file} to temp_invites")

            except Exception as fe:
                print(f"Error processing {file}: {fe}")

        if moved_files:
            print(f"Moved files: {moved_files}")
            repo.git.add(all=True)
            commit_msg = f"Moved {len(moved_files)} expired invites to temp_invites"
            repo.git.commit('-m', commit_msg)
            repo.git.push()
            print("Pushed cleanup changes to GitHub.")
        else:
            print("No expired files found.")

        return jsonify({
            "status": "Cleanup completed",
            "moved_files": moved_files,
            "all_files_now": os.listdir(invites_folder)
        }), 200

    except Exception as e:
        print("Cleanup Error:", str(e))
        return jsonify({
            "error": str(e),
            "message": "An error occurred during cleanup"
        }), 500



if __name__ == "__main__":
    app.run(debug=True)
