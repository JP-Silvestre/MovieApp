db = db.getSiblingDB("movies_db");

const movies = JSON.parse(cat("/docker-entrypoint-initdb.d/init.json"));
db.movies.insertMany(movies);
