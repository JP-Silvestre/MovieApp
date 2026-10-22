# Containerized Movie Explorer

The explorer is a lightweight, decoupled three-tier microservices application designed for isolated container execution across a shared Docker bridge network (movie-net). It enables users to browse and filter a database of movies dynamically by genre (Drama, Comedy, Thriller).

## Architecture Components

**Frontend (movie-ui):**  A lightweight Nginx web server hosting a plain HTML/JavaScript interface. It executes asynchronous fetch calls from the client's browser to retrieve dynamic movie data.

**Backend API (movie-api):** A Python Flask REST API wrapped with Flask-CORS. It handles incoming HTTP requests on port 5001, queries the MongoDB instance over the internal container network, and enforces _id field exclusion for clean JSON serialization.

**Database (movie-db):** A MongoDB 6.0 instance pre-seeded with initial movie documents using mongoimport. It persists data inside the movies_db database on standard port 27017.

| Service | Container Name | Technology | Internal Port | Host Port | Primary Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend** | `movie-ui` | Nginx / HTML / JS | `80` | `8181` | Serves the UI to the client browser |
| **Backend** | `movie-api` | Python 3.10 / Flask | `5000` | `5001` | Processes API requests and queries MongoDB |
| **Database** | `movie-db` | MongoDB 6.0 | `27017` | `27017` | Stores movie documents in `movies_db` |

```
+-----------------------------------------------------------------------------------+
|                                     HOST SYSTEM                                   |
|                                                                                   |
|   +-------------------+                         +-----------------------------+   |
|   |   Web Browser     |                         |    macOS AirPlay Service    |   |
|   |  (Client Machine) |                         |  (Binds to Port 5000: 403)  |   |
|   +---------+---------+                         +-----------------------------+   |
|             |                                                                     |
|             | HTTP Request (http://localhost:8181)                                |
|             v                                                                     |
|   +---------------------------------------------------------------------------+   |
|   |                         DOCKER ENGINE / CONTAINER NETWORK                 |   |
|   |                                                                           |   |
|   |  +--------------------+                                                   |   |
|   |  |     movie-ui       |                                                   |   |
|   |  |  (Nginx Web Server)|                                                   |   |
|   |  +--------------------+                                                   |   |
|   |                                                                           |   |
|   |  Client-Side API Fetch (http://localhost:5001/api/movies?category=...)    |   |
|   |  +-----------------------------------+                                    |   |
|   |  |                                   |                                    |   |
|   |  v                                   v                                    |   |
|   |  +--------------------+  movie-net   +--------------------+               |   |
|   |  |     movie-api      |------------->|      movie-db      |               |   |
|   |  |  (Python/Flask)    |  TCP:27017   |     (MongoDB)      |               |   |
|   |  +--------------------+              +--------------------+               |   |
|   |    Container Port: 5000                Container Port: 27017              |   |
|   |    Host Port: 5001                     Host Port: 27017                   |   |
|   |                                                                           |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

## Step 1: Create the Isolated Bridge Network
```
docker network create movie-net
```

## Step 2: Spin up MongoDB Container & Seed Initial Data
```
docker run -d \
  --name movie-db \
  --network movie-net \
  -p 27017:27017 \
  mongo:6.0

docker cp mongo/init.json movie-db:/tmp/init.json

docker exec -i movie-db mongoimport \
  --db movies_db \
  --collection movies \
  --file /tmp/init.json \
  --jsonArray

docker exec -it movie-db mongosh movies_db --eval "db.movies.find()"
```

## Step 3: Build & Run Python Backend API Container
```
docker build -t movie-backend backend/

docker run -d \
  --name movie-api \
  --network movie-net \
  -p 5001:5000 \
  movie-backend

docker logs --tail 50 movie-api

docker exec -it movie-api python -c "
from pymongo import MongoClient
client = MongoClient('mongodb://movie-db:27017/')
db = client['movies_db']
print(list(db.movies.find({}, {'_id': 0})))
"
```

## Step 4: Build & Run JavaScript Frontend Container
```
docker build -t movie-frontend frontend/

docker run -d \
  --name movie-ui \
  --network movie-net \
  -p 8181:80 \
  movie-frontend
```

## Step5. Verification & Testing
```

http://localhost:8181/

curl -s "http://localhost:5001/api/movies?category=comedy"
```

### Run the Python tests in a container

The test suites use `mongomock`, so they run against an in-memory database and do not need the deployed MongoDB container.

From the `step4_movie-app` directory:

```bash
docker build -f test-runner.Dockerfile -t movie-tests .
docker run --rm movie-tests
```

## Step 6. Clean up the stack
```
# Stop and remove all 3 running containers
docker rm -f movie-ui movie-api movie-db

# Delete custom Docker images
docker rmi movie-frontend movie-backend

# Delete the custom network
docker network rm movie-net

# Optional remove unused system caches and dangling resources
docker system prune -f
```
