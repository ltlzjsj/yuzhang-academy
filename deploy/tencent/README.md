# Tencent Cloud Docker Deployment

This deployment is cloud-light:

- Runs frontend, backend, Celery worker, MySQL, and Redis.
- Does not run Qdrant or any vector database.
- Does not run MinerU. PDF image extraction is disabled and parsing is set to the legacy parser only as a fallback.
- Retrieval on the server is BM25 over MySQL chunks.

## File locations on Tencent Cloud

Use one simple rule:

- Put all images in `/opt/GeoRag/data/images`.
- Put migrated uploaded PDFs/files in `/opt/GeoRag/data/uploads`.
- Put locally generated MinerU output in `/opt/GeoRag/data/mineru_out` if you
  want already-extracted PDF figures to keep displaying.
- Put the project code itself in `/opt/GeoRag`.

The same image folder is used in two ways:

- The backend reads it as the curated gallery image folder.
- The frontend serves it at `http://YOUR_SERVER_IP/static/images/...`.

## 1. Prepare the server

Use the Tencent Cloud instance with Docker CE / Ubuntu 24.04 shown in your console.

Open only the needed firewall ports:

- `80` for HTTP
- `443` if you later add HTTPS
- `22` for SSH, preferably restricted to your IP

## 2. Upload the project

Copy the whole project to the server, for example:

```bash
scp -r GeoRag ubuntu@YOUR_SERVER_IP:/opt/GeoRag
```

Then SSH in:

```bash
ssh ubuntu@YOUR_SERVER_IP
cd /opt/GeoRag/deploy/tencent
```

## 3. Create production env files

```bash
cp backend.env.example backend.env
cp deploy.env.example deploy.env
```

Edit both files:

```bash
nano backend.env
nano deploy.env
```

Required changes:

- `backend.env`: set `MINIMAX_API_KEY`.
- `backend.env`: set a long random `JWT_SECRET`.
- `deploy.env` and `backend.env`: make `DB_PASSWORD` the same value.
- `deploy.env`: change `MYSQL_ROOT_PASSWORD`.
- `backend.env`: set `CORS_ORIGINS` to your domain or server IP, for example `http://YOUR_SERVER_IP`.

## 4. Build and start

```bash
chmod +x up.sh
./up.sh
```

Or run directly:

```bash
docker compose --env-file deploy.env -f docker-compose.yml up -d --build
```

Check status:

```bash
docker compose --env-file deploy.env -f docker-compose.yml ps
docker compose --env-file deploy.env -f docker-compose.yml logs -f backend
```

Open:

```text
http://YOUR_SERVER_IP
```

## 5. Migrate locally parsed data later

Because cloud parsing is intentionally minimal, do the heavy PDF work locally,
then migrate the database and uploaded files to the server.

Typical items to migrate:

- MySQL database data
- `uploads` files if document PDF downloads/previews are needed
- `academy_images` if you want curated image galleries online

The cloud stack stores these in Docker volumes:

- `tencent_mysql_data`
- `/opt/GeoRag/data/uploads`
- `/opt/GeoRag/data/images`
- `/opt/GeoRag/data/mineru_out`

Put all image/static files in:

```bash
/opt/GeoRag/data/images
```

They are available to the backend as curated gallery images and can also be
opened directly at:

```text
http://YOUR_SERVER_IP/static/images/filename.jpg
```

For database migration, export locally with `mysqldump`, upload the dump, then import into the cloud MySQL container.

## 6. Useful commands

Restart:

```bash
docker compose --env-file deploy.env -f docker-compose.yml restart
```

Rebuild after code changes:

```bash
docker compose --env-file deploy.env -f docker-compose.yml up -d --build
```

Stop:

```bash
docker compose --env-file deploy.env -f docker-compose.yml down
```

Backup MySQL:

```bash
docker exec georag-mysql mysqldump -uroot -p georag > georag.sql
```
