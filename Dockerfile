FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py embeddings.py words.py ./
RUN mkdir -p /app/data && wget -q -O /app/data/wiki.kk.vec \
    https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.kk.vec
ENV VECTORS_PATH=/app/data/wiki.kk.vec
ENV CACHE_PATH=/app/data/kk_vectors.npz
ENV ALLOWED_ORIGINS=https://zhasyrynsoz.vercel.app
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```

**4.** **Commit** басыңыз → Build басталады (~15 мин, vectors жүктейді)

Build аяқталғаннан кейін URL шығады:
```
https://whiteraay-zhasyrynsoz-api.hf.space
```

---

## 3️⃣ Frontend → Vercel (тегін)

**1.** [vercel.com](https://vercel.com) → **Sign up with GitHub**

**2.** **Add New Project** → `zhasyrynsoz` repo таңдаңыз

**3.** Мыналарды орнатыңыз:
- **Root Directory:** `frontend` деп жазыңыз
- **Framework Preset:** Vite (автоматты)

**4.** **Environment Variables** бөлімінде:
```
VITE_API_URL = https://whiteraay-zhasyrynsoz-api.hf.space
```

**5.** **Deploy** басыңыз → 2 минутта дайын!

URL шығады:
```
https://zhasyrynsoz.vercel.app