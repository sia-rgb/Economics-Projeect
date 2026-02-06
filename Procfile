web: sh -c 'cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt gunicorn && gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT'
