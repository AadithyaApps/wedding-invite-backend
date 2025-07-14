from flask import Flask, request, jsonify, render_template
from flask import send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)


@app.route("/publish", methods=["POST"])
def publish():
    data = request.get_json()

    file_name = f"{data['groomName'].replace(' ', '')}And{data['brideName'].replace(' ', '')}.html"
    file_path = os.path.join("public_invites", file_name)

    rendered_html = render_template("public_template.html", **data)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    return jsonify({
        "message": "Invite published!",
        "url": f"http://127.0.0.1:5000/public_invites/{file_name}"
    })


@app.route("/public_invites/<filename>")
def serve_invite(filename):
    return send_from_directory("public_invites", filename)


if __name__ == "__main__":
    app.run(debug=True)
