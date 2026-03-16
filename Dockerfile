FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py embeddings.py words.py ./

# Vectors жүктеу
RUN mkdir -p /app/data && wget -q -O /app/data/wiki.kk.vec \
    https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.kk.vec

# Жалғауларды тазалау
COPY clean_vocab.py ./
RUN python3 clean_vocab.py && rm /app/data/wiki.kk.vec

ENV VECTORS_PATH=/app/data/wiki.kk.clean.vec
ENV CACHE_PATH=/app/data/kk_vectors.npz
ENV ALLOWED_ORIGINS=https://zhasyrynsoz.vercel.app
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]