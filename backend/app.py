import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
# Enable CORS for all routes so the browser/frontend can fetch data
CORS(app, resources={r"/*": {"origins": "*"}})

MONGO_URI = os.getenv("MONGO_URI", "mongodb://movie-db:27017/movies_db")

client = MongoClient(MONGO_URI)
db = client.get_database("movies_db")

@app.route("/api/movies", methods=["GET"])
def get_movies():
    try:
        category = request.args.get("category", "").lower().strip()
        query = {"category": category} if category else {}
        
        # Return the public movie fields, including the synopsis, without Mongo's _id.
        movies = list(db.movies.find(query, {
            "_id": 0,
            "title": 1,
            "category": 1,
            "year": 1,
            "description": 1,
        }))
        
        return jsonify({
            "category": category or "all",
            "count": len(movies),
            "movies": movies
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
