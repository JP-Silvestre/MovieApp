db = db.getSiblingDB("movies_db");

const movies = JSON.parse(fs.readFileSync("/docker-entrypoint-initdb.d/init.json", "utf8"));
db.movies.insertMany(movies);
