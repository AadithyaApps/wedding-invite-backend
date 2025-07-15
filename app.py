from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os, git

app = Flask(__name__)
CORS(app)

@app.route("/publish", methods=["POST"])
def publish():
    data = request.get_json()

    groom = data['groomName'].replace(' ', '')
    bride = data['brideName'].replace(' ', '')
    file_name = f"{groom}And{bride}.html"

    # Render the invite using template
    rendered_html = render_template("/templates/public_template.html", **data)

    # Save locally (temporary path)
    local_file_path = os.path.join("/tmp", file_name)
    with open(local_file_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    # GitHub public invites repo
    git_username = os.environ['GIT_USERNAME']
    git_token = os.environ['GIT_TOKEN']
    repo_url = f"https://{git_username}:{git_token}@github.com/AadithyaApps/wedding-invite-public.git"
    repo_dir = "/tmp/wedding-invite-public"

    # Clone if not already cloned
    if not os.path.exists(repo_dir):
        git.Repo.clone_from(repo_url, repo_dir)
    repo = git.Repo(repo_dir)

    # Move file into public-invites folder
    invites_folder = os.path.join(repo_dir, 'public-invites')
    os.makedirs(invites_folder, exist_ok=True)
    final_file_path = os.path.join(invites_folder, file_name)
    os.replace(local_file_path, final_file_path)



    repo.git.config('user.email', 'aadithya.ofc@gmail.com')
    repo.git.config('user.name', 'Aadithya Sridharan')


    # Git commit and push
    repo.git.add(all=True)
    repo.git.commit('-m', f"Added invite for {groom} and {bride}")
    repo.git.push()

    # Return public Netlify URL
    netlify_url = f"https://your-netlify-site.netlify.app/public-invites/{file_name}"

    return jsonify({
        "message": "Invite published!",
        "url": netlify_url
    })

if __name__ == "__main__":
    app.run(debug=True)
