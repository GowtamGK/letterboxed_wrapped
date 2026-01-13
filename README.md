# 🎬 Letterboxd Wrapped
<img width="1113" height="831" alt="image" src="https://github.com/user-attachments/assets/1e70abe2-99d6-414f-8e40-3f9b2cf8b0a3" />


**Your Year in Film** - A beautiful, Spotify Wrapped-style visualization for your Letterboxd viewing history!

## ✨ Features

- 📊 **Complete Year Stats** - Films watched, hours spent, reviews written
- ⭐ **Rating Analysis** - Average rating, distribution across all your ratings
- 🎭 **Genre DNA** - See which genres dominated your year
- 🎬 **Top Directors & Actors** - Who appeared most on your screen
- 🏆 **Highest & Lowest Rated** - Your best and worst films of the year
- 🎪 **Movie Era** - Get your personalized movie-watching personality
- 📱 **Share Ready** - Beautiful slides perfect for sharing

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Chrome (for Selenium)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/letterboxd-wrapped.git
cd letterboxd-wrapped
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run the app**
```bash
python app.py
```

4. **Open browser** to `http://localhost:5000`

5. **Enter any public Letterboxd username** and select a year!

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Flask (Python) |
| Scraping | Selenium + BeautifulSoup4 |
| Browser Automation | Chrome + WebDriver Manager |
| Frontend | Vanilla HTML/CSS/JavaScript |
| Styling | Custom CSS with Letterboxd-inspired dark theme |

## 📱 How It Works

1. Enter a Letterboxd username and select a year
2. **Selenium** scrapes the Year in Review page (requires JavaScript rendering)
3. **Requests** scrapes all ratings from the reviews pages (with pagination)
4. Both scrapes run **in parallel** for faster loading (~15 seconds)
5. Data is analyzed and beautiful animated slides are generated
6. Share your results!

## 🌐 Deployment

### Deploy to Render (Recommended)

1. Push to GitHub
2. Create new **Web Service** on [Render](https://render.com)
3. Connect your GitHub repo
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. Add environment variable for Chrome:
   ```
   CHROME_BIN=/usr/bin/google-chrome
   ```

### Docker (Alternative)

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y chromium chromium-driver
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
```

## ⚡ Performance

- **Parallel scraping** - Year page and reviews fetched simultaneously
- **Optimized waits** - Minimal delays for Selenium
- **Threaded server** - Handles multiple requests efficiently
- **Typical load time**: 12-18 seconds

## 📂 Project Structure

```
letterboxd_wrapped/
├── app.py              # Flask backend + scraping logic
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Frontend (HTML/CSS/JS)
└── README.md
```

## ⚠️ Notes

- This app scrapes **public** Letterboxd profiles only
- Selenium requires Chrome/Chromium browser installed
- Please use responsibly - don't spam requests
- First request may be slower (ChromeDriver setup)

## 📝 License

MIT - Feel free to use and modify!

---

Made with 🍿 for movie lovers everywhere

