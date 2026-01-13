"""
Letterboxd Wrapped 2.0 - Complete Cinematic Year in Review
Uses Selenium for full JavaScript rendering to capture all data
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import time
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
CORS(app)

# Cache for selenium driver
_driver = None

def get_driver():
    """Get or create a headless Chrome driver"""
    global _driver
    if _driver is None:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # Use pre-installed ChromeDriver if available (Docker), otherwise use webdriver-manager
        import os
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
        if os.path.exists(chromedriver_path):
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())
        _driver = webdriver.Chrome(service=service, options=options)
    return _driver

def get_poster_url(film_id, slug, size=500):
    """Construct poster URL from film ID and slug"""
    if not film_id or not slug:
        return ''
    id_str = str(film_id)
    id_path = '/'.join(list(id_str))
    return f"https://a.ltrbxd.com/resized/film-poster/{id_path}/{film_id}-{slug}-0-{size}-0-{int(size*1.5)}-crop.jpg"

def scrape_all_rated_films(username, year):
    """Scrape ALL rated films from user's reviews page with pagination"""
    all_films = []
    page = 1
    max_pages = 10
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        while page <= max_pages:
            # Use reviews page - has all films with ratings and reviews for the year
            if page == 1:
                url = f"https://letterboxd.com/{username}/reviews/films/for/{year}/"
            else:
                url = f"https://letterboxd.com/{username}/reviews/films/for/{year}/page/{page}/"
            
            print(f"Scraping reviews page {page}: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Reviews page uses div.listitem with article.production-viewing
            entries = soup.select('div.listitem article.production-viewing')
            print(f"Found {len(entries)} review entries on page {page}")
            
            if not entries:
                break
            
            for entry in entries:
                film = {}
                
                # Get film data from the figure div with data attributes
                figure = entry.select_one('div.react-component.figure')
                if figure:
                    film['film_id'] = figure.get('data-film-id', '')
                    film['slug'] = figure.get('data-item-slug', '')
                    film['title'] = figure.get('data-item-name', '')
                    if film['film_id'] and film['slug']:
                        film['poster'] = get_poster_url(film['film_id'], film['slug'])
                
                # Rating span has class like "rated-10" (10 = 5 stars)
                rating_span = entry.select_one('span.rating')
                if rating_span:
                    classes = rating_span.get('class', [])
                    for cls in classes:
                        if cls.startswith('rated-'):
                            try:
                                rating_val = int(cls.replace('rated-', ''))
                                film['rating'] = rating_val / 2
                            except ValueError:
                                pass
                    film['stars'] = rating_span.get_text(strip=True)
                
                if film.get('title') and film.get('rating'):
                    all_films.append(film)
            
            # Check for next page
            next_link = soup.select_one('.paginate-nextprev a.next')
            if not next_link:
                break
            
            page += 1
        
        print(f"Total rated films found: {len(all_films)}")
        return all_films
        
    except Exception as e:
        print(f"Error scraping rated films: {e}")
        return all_films

def scrape_with_selenium(username, year):
    """Use Selenium to scrape the fully-rendered year page"""
    url = f"https://letterboxd.com/{username}/year/{year}/"
    
    data = {
        'username': username,
        'display_name': username,
        'profile_pic': '',
        'year': year,
        'films_logged': 0,
        'hours_watched': 0,
        'reviews': 0,
        'likes': 0,
        'top_films': [],
        'genres': [],
        'countries': [],
        'themes': [],
        'directors': [],
        'actors': [],
        'milestones': {},
        'rating_spread': {},
        'films_list': []
    }
    
    try:
        driver = get_driver()
        driver.get(url)
        
        # Wait for page to load (reduced from 3s to 1.5s)
        time.sleep(1.5)
        
        # Get page source after JS rendering
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # === PROFILE INFO ===
        profile_link = soup.select_one('a.avatar img, .profile-avatar img')
        if profile_link:
            data['profile_pic'] = profile_link.get('src', '')
        
        display_name = soup.select_one('.displayname, .yir-header .displayname')
        if display_name:
            data['display_name'] = display_name.get_text(strip=True)
        
        # === MAIN STATS ===
        # Look for stat blocks in yir-member-stats (65 Diary Entries, 119.3 Hours, etc.)
        stat_items = soup.select('.yir-member-statistic, .yir-statistic, .profile-stats li')
        
        for item in stat_items:
            # Get value and definition from spans
            value_span = item.select_one('span.value')
            def_span = item.select_one('span.definition')
            
            if value_span and def_span:
                try:
                    num = float(value_span.get_text(strip=True).replace(',', ''))
                    definition = def_span.get_text(strip=True).lower()
                    
                    if 'diary' in definition or 'entries' in definition:
                        data['films_logged'] = int(num)
                    elif 'hour' in definition:
                        data['hours_watched'] = num
                    elif 'review' in definition:
                        data['reviews'] = int(num)
                    elif 'like' in definition:
                        data['likes'] = int(num)
                except ValueError:
                    pass
            else:
                # Fallback: extract from text
                text = item.get_text(strip=True).lower()
                num_match = re.search(r'([\d,.]+)', text)
                if num_match:
                    try:
                        num = float(num_match.group(1).replace(',', ''))
                        if 'diary' in text or 'entries' in text:
                            data['films_logged'] = int(num)
                        elif 'hour' in text:
                            data['hours_watched'] = num
                        elif 'review' in text:
                            data['reviews'] = int(num)
                        elif 'like' in text:
                            data['likes'] = int(num)
                    except ValueError:
                        pass
        
        # === HIGHEST RATED FILMS ===
        highest_section = soup.select_one('.yir-highest-rated, section[data-section="highest-rated"]')
        if highest_section:
            for item in highest_section.select('li')[:12]:
                film = {}
                
                # Get from data attributes
                poster_div = item.select_one('div[data-film-id]')
                if poster_div:
                    film['title'] = poster_div.get('data-film-name', poster_div.get('data-item-name', ''))
                    film['film_id'] = poster_div.get('data-film-id', '')
                    film['slug'] = poster_div.get('data-film-slug', poster_div.get('data-item-slug', ''))
                    film['poster'] = get_poster_url(film['film_id'], film['slug'])
                
                # Get rating
                rating_span = item.select_one('.rating')
                if rating_span:
                    film['stars'] = rating_span.get_text(strip=True)
                    # Count stars
                    full = film['stars'].count('★')
                    half = 0.5 if '½' in film['stars'] else 0
                    film['rating'] = full + half
                
                # Fallback: get title from alt text
                if not film.get('title'):
                    img = item.select_one('img')
                    if img:
                        alt = img.get('alt', '')
                        film['title'] = re.sub(r'^Poster for ', '', alt)
                
                if film.get('title'):
                    data['top_films'].append(film)
        
        # === GENRES ===
        # Look for genre breakdown
        genre_section = soup.select_one('.yir-genres, .film-breakdown-graph')
        if genre_section:
            for bar in genre_section.select('.film-breakdown-graph-bar, a[href*="/genre/"]'):
                label = bar.select_one('.film-breakdown-graph-bar-label, a')
                count_elem = bar.select_one('.film-breakdown-graph-bar-value span, span')
                
                if label:
                    name = label.get_text(strip=True)
                    count = 0
                    if count_elem:
                        count_text = count_elem.get_text(strip=True)
                        count_match = re.search(r'(\d+)', count_text)
                        if count_match:
                            count = int(count_match.group(1))
                    
                    if name and len(name) < 30 and name not in [g['name'] for g in data['genres']]:
                        data['genres'].append({'name': name, 'count': count})
        
        # Fallback: Extract from href patterns
        if not data['genres']:
            for link in soup.select(f'a[href*="/{username}/diary/for/{year}/genre/"]'):
                name = link.get_text(strip=True)
                # Find sibling with count
                parent = link.parent
                if parent:
                    count_text = parent.get_text(strip=True)
                    count_match = re.search(r'(\d+)\s*films?', count_text, re.I)
                    count = int(count_match.group(1)) if count_match else 0
                    
                    if name and len(name) < 30 and name not in [g['name'] for g in data['genres']]:
                        data['genres'].append({'name': name, 'count': count})
        
        # === COUNTRIES ===
        for link in soup.select(f'a[href*="/{username}/diary/for/{year}/country/"]'):
            name = link.get_text(strip=True)
            parent = link.parent
            if parent:
                count_text = parent.get_text(strip=True)
                count_match = re.search(r'(\d+)\s*films?', count_text, re.I)
                count = int(count_match.group(1)) if count_match else 0
                
                if name and len(name) < 30 and name not in [c['name'] for c in data['countries']]:
                    data['countries'].append({'name': name, 'count': count})
        
        # === THEMES ===
        themes_section = soup.select_one('.yir-themes, section[data-section="themes"]')
        if themes_section:
            for item in themes_section.select('li')[:5]:
                link = item.select_one('a')
                if link:
                    text = link.get_text(strip=True)
                    # Split into theme name and count
                    match = re.match(r'(.+?)\s*(\d+)\s*films?', text, re.I)
                    if match:
                        data['themes'].append({
                            'name': match.group(1).strip(),
                            'count': int(match.group(2))
                        })
        
        # === DIRECTORS ===
        # Find all director links on the page
        director_links = soup.select(f'a[href*="/with/director/"]')
        seen_directors = set()
        
        for link in director_links:
            href = link.get('href', '')
            # Only get links for this user's diary
            if f'/{username}/' in href and f'/{year}/' in href:
                name = link.get_text(strip=True)
                # Skip if it's just a number or too short
                if name and len(name) > 2 and not name.isdigit() and 'films' not in name.lower():
                    if name not in seen_directors:
                        seen_directors.add(name)
                        data['directors'].append({'name': name})
                        if len(data['directors']) >= 5:
                            break
        
        # === ACTORS ===
        # Find all actor links on the page
        actor_links = soup.select(f'a[href*="/with/actor/"]')
        seen_actors = set()
        
        for link in actor_links:
            href = link.get('href', '')
            # Only get links for this user's diary
            if f'/{username}/' in href and f'/{year}/' in href:
                name = link.get_text(strip=True)
                # Skip if it's just a number or too short
                if name and len(name) > 2 and not name.isdigit() and 'films' not in name.lower():
                    if name not in seen_actors:
                        seen_actors.add(name)
                        data['actors'].append({'name': name})
                        if len(data['actors']) >= 8:
                            break
        
        # === MILESTONES ===
        milestones_section = soup.select_one('.yir-milestones, section:has(h3:contains("Milestones"))')
        if milestones_section:
            for item in milestones_section.select('.yir-milestone, li'):
                title_elem = item.select_one('.title, h4')
                poster_elem = item.select_one('div[data-film-name]')
                date_elem = item.select_one('.date, time')
                
                if title_elem:
                    milestone_type = title_elem.get_text(strip=True).lower()
                    if poster_elem:
                        film_name = poster_elem.get('data-film-name', '')
                        film_id = poster_elem.get('data-film-id', '')
                        slug = poster_elem.get('data-film-slug', '')
                        date = date_elem.get_text(strip=True) if date_elem else ''
                        
                        if 'first' in milestone_type:
                            data['milestones']['first'] = {
                                'title': film_name,
                                'poster': get_poster_url(film_id, slug),
                                'date': date
                            }
                        elif 'last' in milestone_type:
                            data['milestones']['last'] = {
                                'title': film_name,
                                'poster': get_poster_url(film_id, slug),
                                'date': date
                            }
        
        # === HIGHS AND LOWS ===
        data['highs_lows'] = {}
        
        # Look for the highs and lows section items
        for section in soup.select('section, div'):
            # Find items with labels like "Most Popular", "Most Obscure", etc.
            items = section.select('li, .stat-item, div.film-stat')
            for item in items:
                text = item.get_text(strip=True).lower()
                poster = item.select_one('div[data-film-name], div[data-item-name]')
                
                if poster:
                    film_data = {
                        'title': poster.get('data-film-name', poster.get('data-item-name', '')),
                        'film_id': poster.get('data-film-id', ''),
                        'slug': poster.get('data-film-slug', poster.get('data-item-slug', ''))
                    }
                    film_data['poster'] = get_poster_url(film_data['film_id'], film_data['slug'])
                    
                    if 'most popular' in text:
                        data['highs_lows']['most_popular'] = film_data
                    elif 'most obscure' in text:
                        data['highs_lows']['most_obscure'] = film_data
                    elif 'longest' in text:
                        data['highs_lows']['longest'] = film_data
                    elif 'shortest' in text:
                        data['highs_lows']['shortest'] = film_data
                    elif 'newest' in text:
                        data['highs_lows']['newest'] = film_data
                    elif 'oldest' in text:
                        data['highs_lows']['oldest'] = film_data
        
        # === FILMS LIST (all watched) ===
        films_grid = soup.select_one('.poster-list, .yir-films-grid')
        if films_grid:
            for item in films_grid.select('li, .film-poster')[:20]:
                poster_div = item.select_one('div[data-film-name]')
                if poster_div:
                    data['films_list'].append({
                        'title': poster_div.get('data-film-name', ''),
                        'poster': get_poster_url(
                            poster_div.get('data-film-id', ''),
                            poster_div.get('data-film-slug', '')
                        )
                    })
        
        return data
        
    except Exception as e:
        print(f"Selenium scraping error: {e}")
        import traceback
        traceback.print_exc()
        return None

def scrape_profile_basic(username):
    """Quick scrape of profile for basic info (no Selenium needed)"""
    url = f"https://letterboxd.com/{username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        data = {
            'display_name': username,
            'profile_pic': '',
            'total_films': 0,
            'rating_distribution': {},
            'average_rating': 0
        }
        
        # Display name
        name = soup.select_one('span.displayname')
        if name:
            data['display_name'] = name.get_text(strip=True)
        
        # Avatar
        avatar = soup.select_one(f'img[alt="{data["display_name"]}"]')
        if avatar:
            data['profile_pic'] = avatar.get('src', '')
        
        # Total films
        for stat in soup.select('h4.profile-statistic'):
            value = stat.select_one('span.value')
            label = stat.select_one('span.definition')
            if value and label:
                v = value.get_text(strip=True).replace(',', '')
                l = label.get_text(strip=True).lower()
                if 'film' in l and 'this year' not in l:
                    data['total_films'] = int(v) if v.isdigit() else 0
        
        # Rating distribution
        rating_section = soup.select_one('section.ratings-histogram-chart')
        if rating_section:
            rating_map = {
                '½': 0.5, '★': 1, '★½': 1.5, '★★': 2, '★★½': 2.5,
                '★★★': 3, '★★★½': 3.5, '★★★★': 4, '★★★★½': 4.5, '★★★★★': 5
            }
            
            total_weighted = 0
            total_count = 0
            
            for link in rating_section.select('a.bar[data-original-title]'):
                title = link.get('data-original-title', '')
                match = re.match(r'(\d+)\s+([\u2605\u00bd]+)\s+ratings?', title)
                if match:
                    count = int(match.group(1))
                    stars = match.group(2)
                    rating_val = rating_map.get(stars, 0)
                    
                    if rating_val > 0:
                        data['rating_distribution'][str(rating_val)] = count
                        total_weighted += count * rating_val
                        total_count += count
            
            if total_count > 0:
                data['average_rating'] = round(total_weighted / total_count, 2)
                data['total_ratings'] = total_count
        
        return data
        
    except Exception as e:
        print(f"Profile scrape error: {e}")
        return None

def get_personality(avg_rating, five_star_pct, total):
    """Generate rating personality"""
    if total == 0 or not avg_rating:
        return {
            'type': 'The Cinephile',
            'emoji': '🎬',
            'tagline': 'A true film lover',
            'description': 'You watch films for the experience, not the ratings.'
        }
    
    if avg_rating >= 4.5:
        return {
            'type': 'The Enthusiast',
            'emoji': '💖',
            'tagline': 'You adore almost everything',
            'description': f'★{avg_rating:.1f} average — Cinema brings you pure joy!'
        }
    elif avg_rating >= 4.0:
        return {
            'type': 'The Generous Soul',
            'emoji': '😊',
            'tagline': 'You see the best in films',
            'description': f'★{avg_rating:.1f} average — You appreciate the craft.'
        }
    elif avg_rating >= 3.5:
        return {
            'type': 'The Balanced Viewer',
            'emoji': '⚖️',
            'tagline': 'Fair and thoughtful',
            'description': f'★{avg_rating:.1f} average — The Goldilocks of critics.'
        }
    elif avg_rating >= 3.0:
        return {
            'type': 'The Discerning Eye',
            'emoji': '🧐',
            'tagline': 'Quality over quantity',
            'description': f'★{avg_rating:.1f} average — Only the good stuff impresses you.'
        }
    else:
        return {
            'type': 'The Tough Critic',
            'emoji': '🎯',
            'tagline': 'High standards, always',
            'description': f'★{avg_rating:.1f} average — Masterpieces only, please.'
        }

def get_movie_era(genres):
    """Determine movie era from top genre"""
    if not genres:
        return {'era': 'Eclectic Explorer', 'subtitle': 'No single genre could contain you', 'emoji': '🎬'}
    
    top = genres[0]['name'].lower()
    
    eras = {
        'comedy': {'era': 'Feel-Good Cinema', 'subtitle': 'Laughter was your medicine', 'emoji': '😂'},
        'horror': {'era': 'Dark Depths', 'subtitle': 'You lived in the shadows', 'emoji': '🖤'},
        'thriller': {'era': 'Edge of Your Seat', 'subtitle': 'Suspense was your addiction', 'emoji': '😰'},
        'drama': {'era': 'Emotional Depths', 'subtitle': 'Drama had you in a chokehold', 'emoji': '🎭'},
        'action': {'era': 'Adrenaline Rush', 'subtitle': 'Pure cinema energy', 'emoji': '💥'},
        'romance': {'era': 'Hopeless Romantic', 'subtitle': 'Love stories hit different', 'emoji': '💕'},
        'sci-fi': {'era': 'Future Forward', 'subtitle': 'Reality was too boring', 'emoji': '🚀'},
        'documentary': {'era': 'Truth Seeker', 'subtitle': 'Real stories fascinated you', 'emoji': '📚'},
        'animation': {'era': 'Animated Dreams', 'subtitle': 'Animation is cinema', 'emoji': '✨'},
        'mystery': {'era': 'Puzzle Master', 'subtitle': 'You loved the chase', 'emoji': '🔍'},
        'crime': {'era': 'Criminal Minds', 'subtitle': 'The underworld called', 'emoji': '🔫'},
    }
    
    for key, val in eras.items():
        if key in top:
            return val
    
    return {'era': 'Eclectic Explorer', 'subtitle': 'No single genre could contain you', 'emoji': '🎬'}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/wrapped/<username>/<int:year>')
def get_wrapped(username, year):
    """Main API endpoint"""
    
    # Get profile basics first (fast)
    profile = scrape_profile_basic(username)
    if not profile:
        return jsonify({'error': f'User "{username}" not found'})
    
    # Run Selenium scrape and reviews scrape IN PARALLEL for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        selenium_future = executor.submit(scrape_with_selenium, username, year)
        reviews_future = executor.submit(scrape_all_rated_films, username, year)
        
        year_data = selenium_future.result()
        all_rated_films = reviews_future.result()
    
    if not year_data:
        return jsonify({'error': f'Could not load data for {year}'})
    
    # Merge data
    result = {
        'username': username,
        'display_name': year_data.get('display_name') or profile['display_name'],
        'profile_pic': year_data.get('profile_pic') or profile['profile_pic'],
        'year': year,
        
        # Core stats
        'films_logged': year_data.get('films_logged', 0),
        'hours_watched': year_data.get('hours_watched', 0),
        'reviews': year_data.get('reviews', 0),
        'likes': year_data.get('likes', 0),
        
        # Derived stats
        'minutes_watched': int(year_data.get('hours_watched', 0) * 60),
        'days_equivalent': round(year_data.get('hours_watched', 0) / 24, 1),
        
        # Content
        'top_films': year_data.get('top_films', [])[:12],
        'genres': year_data.get('genres', [])[:10],
        'countries': year_data.get('countries', [])[:5],
        'themes': year_data.get('themes', [])[:5],
        'directors': year_data.get('directors', [])[:5],
        'actors': year_data.get('actors', [])[:8],
        'milestones': year_data.get('milestones', {}),
        'highs_lows': year_data.get('highs_lows', {}),
        'films_list': year_data.get('films_list', [])[:16],
        
        # Profile stats (will be overwritten if we calculate from films)
        'rating_distribution': profile.get('rating_distribution', {}),
        'average_rating': profile.get('average_rating', 0),
        'total_ratings': profile.get('total_ratings', 0),
        'star_distribution': {},
        'highest_rated_film': None,
        'lowest_rated_film': None,
    }
    
    # Calculate rating stats from ALL rated films (already fetched in parallel above)
    result['five_star_pct'] = 0  # Default value
    rated_films = all_rated_films if all_rated_films else [f for f in result['top_films'] if f.get('rating')]
    
    if rated_films:
        # Calculate average
        avg = sum(f['rating'] for f in rated_films) / len(rated_films)
        result['average_rating'] = round(avg, 2)
        result['total_ratings'] = len(rated_films)
        
        # Build rating distribution (count per star level)
        star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for f in rated_films:
            r = f.get('rating', 0)
            # Round to nearest whole star for distribution
            star = min(5, max(1, round(r)))
            star_counts[star] += 1
        
        result['star_distribution'] = star_counts
        result['five_star_pct'] = (star_counts[5] / len(rated_films)) * 100 if rated_films else 0
        
        # Find highest and lowest rated films (with posters)
        sorted_by_rating = sorted(rated_films, key=lambda x: x.get('rating', 0), reverse=True)
        if sorted_by_rating:
            result['highest_rated_film'] = sorted_by_rating[0]
            # Get lowest that's different from highest
            for film in reversed(sorted_by_rating):
                if film.get('title') != sorted_by_rating[0].get('title'):
                    result['lowest_rated_film'] = film
                    break
    
    # Generate personality and era
    result['personality'] = get_personality(result['average_rating'], result['five_star_pct'], result['total_ratings'])
    result['movie_era'] = get_movie_era(result['genres'])
    
    return jsonify(result)

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
