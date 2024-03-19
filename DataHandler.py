from FilmDetails import FilmDetails, Person, Film
from bs4 import BeautifulSoup
from collections import Counter
import sqlite3
import requests
import json
import re
from datetime import datetime 

class DataHandler:
    TMDB_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIzYTAwZDZlNGFkNzQyYTY0MTZmNjEwYTE0N2E4ODA2NCIsInN1YiI6IjY1OWVlNWVjOTFiNTMwMDFmZGYxZGMxOSIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.r1uBAc6yrAsFwJxICmap8RrNk8Cf_w1RIwlrwTu4aPM"

    def __init__(self):
        self.populating_movies = []
        self.unreadable_films = []

        self.films = []
        self.diary = []
        self.watchlist = []
        
        self.temp_title = None
        self.temp_date = None
        self.average_rating = 0.0
        self.user_rating = None

    def check_record_exists(self,url,cursor,date_added):
        exists = False
        statement = "SELECT film.id, film.title, film.release_year, film.letterboxd_url, GROUP_CONCAT(DISTINCT g.name) AS genres, GROUP_CONCAT(DISTINCT fc.country) AS countries, film.runtime, film.image, film.rating \
                    FROM film \
                    LEFT JOIN film_genre AS fg ON film.id = fg.film_id \
                    LEFT JOIN genre AS g ON fg.genre_id = g.id \
                    LEFT JOIN film_country AS fc ON fc.film_id = film.id \
                    WHERE film.letterboxd_url = ? \
                    GROUP BY film.id;"
        cursor.execute(statement, (url,))
        row = cursor.fetchone()

        if row:
            id, title, release_year, letterboxd_url, genres_str, countries_str, runtime, image_url, rating = row
            if genres_str != None:
                genres = genres_str.split(",")
            else:
                genres = ""
            if countries_str != None:
                production_countries = countries_str.split(",")
            else:
                production_countries = ""

            cast = []
            crew = []

            statement = "SELECT pcrew.person_id, p.name, pcrew.job, p.image \
                        FROM film_person_crew AS pcrew \
                        INNER JOIN person AS p ON pcrew.person_id = p.id \
                        WHERE film_id = ?"
            cursor.execute(statement, (id,))
            crew_row = cursor.fetchall()
            for c in crew_row:
                p_id, p_name, p_job, p_image = c
                crew.append(Person(p_id, p_name, job=p_job, p_image=p_image))

            self.populating_movies.append(Film(title, release_year, letterboxd_url, id, FilmDetails(genres, production_countries, runtime, cast, crew, image_url, rating, self.user_rating)))
            exists = True

        return exists
    
    def process_data(self,data,choice):

        self.populating_movies = []
        
        conn = sqlite3.connect('database/FilmDataDB.db')
        cursor = conn.cursor()

        for item in data:

            url = item
            self.user_rating = None
            date_added = None

            if not self.check_record_exists(url,cursor,date_added):                

                page = requests.get(url)
                soup = BeautifulSoup(page.content,"html.parser")
                tmdb_link = soup.find("a", {"class": "micro-button track-event", "data-track-action": "TMDb", "target": "_blank"})
                average_rating_label = soup.find("meta", {"name": "twitter:label2", "content": "Average rating"})

                if average_rating_label:
                    next_sibling = average_rating_label.find_next_sibling("meta")
                    if next_sibling:
                        average_rating = next_sibling["content"]
                        average_rating = re.search(r'(\d+\.\d+|\d+)', average_rating)
                        if average_rating:
                            self.average_rating = float(average_rating.group(1))

                if tmdb_link:
                    tmdb_url = tmdb_link.get("href")

                    if "tv" not in tmdb_url:  
                        tmdb_id = tmdb_url.split("/")[-2]  # Extract TMDB ID from the URL
                        details = self.parse_api(tmdb_id,cursor)

                        if details:
                            cursor.execute(f"INSERT INTO film (id, title, release_year, runtime, letterboxd_url, image, rating) VALUES (?,?,?,?,?,?,?)",(tmdb_id, self.temp_title, self.temp_date, details.runtime, url, details.image_url,self.average_rating))
                            
                            for g in details.genres:
                                cursor.execute("INSERT INTO film_genre (film_id, genre_id) VALUES (?,?)",(tmdb_id,int(g["id"])))
                            for c in details.production_countries:
                                cursor.execute("INSERT INTO film_country (film_id, country) VALUES (?,?)",(tmdb_id,c))

                            for p in details.crew:
                                cursor.execute("SELECT * FROM film_person_crew WHERE film_id = ? AND person_id = ? AND job = ?", (tmdb_id, p.id, p.job))
                                existing_record = cursor.fetchone()
                                
                                if existing_record is None:
                                    cursor.execute("INSERT INTO film_person_crew (film_id, person_id, job) VALUES (?, ?, ?)", (tmdb_id, p.id, p.job))
                                else:
                                    print(f"Record with film_id={tmdb_id} and person_id={p.id} already exists.")

                            if self.temp_date == None:
                                self.temp_date = 0

                            self.populating_movies.append(Film(self.temp_title,self.temp_date,url,tmdb_id,details))
                            conn.commit()
                        
                        else:
                            self.unreadable_films.append(f"{url} : NOT IN DB")
                    else:
                        #not readaable as they are a TV show
                        self.unreadable_films.append(f"{url} : TV SHOW")
                else:
                    print(f"{url}: Could Not Find TMDb Link")
        conn.close()

        if choice == 'f':
            self.films = self.populating_movies
        elif choice == 'w':
            self.watchlist = self.populating_movies
        elif choice == 'd':
            self.diary = self.populating_movies

    def process_providers(self,data):
        for film in data:
            film.details.providers, film.details.still_img = self.get_providers(film.id)
        
        return data

    def get_providers(self,id):
        url_providers = f"https://api.themoviedb.org/3/movie/{id}/watch/providers"
        url_img = f"https://api.themoviedb.org/3/movie/{id}/images"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.TMDB_API_KEY}"
        }

        response_providers = requests.get(url_providers, headers=headers)
        response_img = requests.get(url_img, headers=headers)

        film_providers = json.loads(response_providers.text)
        film_img = json.loads(response_img.text)

        if film_img['backdrops']:       
            if film_img['backdrops'][0]:
                img = film_img['backdrops'][0]['file_path']
        else:
            img = None

        return film_providers['results'], img

    def get_tmdb_film_data(self, id):
        url_details = f"https://api.themoviedb.org/3/movie/{id}?language=en-US"
        url_credits = f"https://api.themoviedb.org/3/movie/{id}/credits?language=en-US"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.TMDB_API_KEY}"
        }

        response_details = requests.get(url_details, headers=headers)
        response_credits = requests.get(url_credits, headers=headers)

        film_details = json.loads(response_details.text)
        film_credits = json.loads(response_credits.text)


        return film_details, film_credits
    
    #Get API info for a single movie using ID
    def parse_api(self,id,cursor):
        complete_data_details, complete_data_credits = self.get_tmdb_film_data(id)
            
        if 'success' not in complete_data_details:
            
            self.temp_date = complete_data_details["release_date"][:4] if complete_data_details["release_date"] != "" else 0
            self.temp_title = complete_data_details["title"]
            image_url = complete_data_details["poster_path"]

            people = self.insert_person_db(complete_data_credits,cursor)

            runtime = complete_data_details["runtime"] if complete_data_details["runtime"] != "" else 0
            genres = [{"id": g["id"], "name": g["name"]} for g in complete_data_details["genres"]]
            production_countries = [c["name"] for c in complete_data_details["production_countries"]]
            
            # Separate cast and crew
            crew = [Person(p["id"], p["name"], job=p["job"], p_image=p["profile_path"]) for p in people if "character" not in p]

            return FilmDetails(genres, production_countries, runtime, [], crew, image_url, self.average_rating, self.user_rating)
        else:
            return None

    #inserting  each cast & crew member into the database
    def insert_person_db(self,credits,cursor):
        people = credits['crew']

        for p in people:
            statement = "SELECT * from person WHERE person.id = ?"
            cursor.execute(statement, (p["id"],))
            row = cursor.fetchone()
            if not row:
                cursor.execute("INSERT INTO person (id, name, image) VALUES (?,?,?)",(int(p["id"]),(p["name"]),(str(p["profile_path"]))))
        return people

    #only needed to run once
    def insert_genre_db(self):
        conn = sqlite3.connect('database/FilmDataDB.db')
        cursor = conn.cursor()

        statement = "SELECT * FROM genre"
        cursor.execute(statement)
        genre_row = cursor.fetchall()

        if not genre_row:
            url = "https://api.themoviedb.org/3/genre/movie/list"

            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {self.TMDB_API_KEY}"
            }

            response = requests.get(url, headers=headers)

            genres = json.loads(response.text)

            for i in genres["genres"]:

                cursor.execute("INSERT INTO genre (id, name) VALUES (?,?)",(i["id"],i["name"]))
                       
        conn.commit()
        conn.close()
    