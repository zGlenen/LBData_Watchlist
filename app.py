from flask import Flask, render_template, request, jsonify
from flask_paginate import Pagination, get_page_parameter
import json
from UserScraper import UserScraper
from  DataHandler import DataHandler

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():   
    usernames = request.form.getlist('usernames[]')
    scraper = UserScraper()
    data_handler = DataHandler()
    data_handler.insert_genre_db()
    user_urls = {}

    for username in usernames:
        watchlist_films = scraper.scrape_user(username, "watchlist")
        if watchlist_films == False:
            return jsonify({'error': 'One or more usernames don\'t exist. Please try again.'}), 400
        user_urls[username] = set(scraper.get_uris(watchlist_films))

    common_urls = set.intersection(*user_urls.values())
    data_handler.process_data(common_urls,'w')

    similar_films = data_handler.process_providers(data_handler.watchlist)

    serialized_similar_films = []
    for i in similar_films:
        film = serialize_film(i)
        serialized_similar_films.append(film)

    write_to_file(serialized_similar_films,'serialized_films.json')

    return jsonify(True)
    
@app.route('/films')
def films():
    similar_films = read_from_file('serialized_films.json')
    filtered_films = read_from_file('filtered_films.json')

    filter_options = request.args
    filtered = request.args.get('filtered', type=str) 
    filtered = filtered == 'True'

    for i in filter_options:
        if i.startswith("gen_") or i.startswith("provider_") or i.startswith("run_"):
            filtered_films = get_filtered_films(filter_options,similar_films)
            filtered = True
            break
        if i.startswith("blank"):
            filtered_films = similar_films
            filtered = False
            break

    if filtered and not filtered_films:
        filtered_films = []

    if not similar_films:
        return render_template('error.html')
            
    sorting_option = request.args.get('sorting_option', default='year_latest', type=str)
    sorted_films = get_sorted_films(filtered_films,sorting_option)

    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 20  # Number of films per page
    offset = (page - 1) * per_page

    paginated_films = sorted_films[offset: offset + per_page]

    pagination = Pagination(page=page, total=len(filtered_films if filtered else sorted_films), per_page=per_page, css_framework='bootstrap')
    write_to_file(filtered_films,'filtered_films.json')

    
    return render_template('films.html',pagination=pagination,data=similar_films,isFiltered=filtered,filtered_films=paginated_films)

def write_to_file(serialized_films, filename):
    with open(filename, 'w') as file:
        json.dump(serialized_films, file)

# Function to read serialized films from a file
def read_from_file(filename):
    try:
        with open(filename, 'r') as file:
            serialized_films = json.load(file)
        return serialized_films
    except FileNotFoundError:
        # Handle case where file is not found
        return []
    except json.JSONDecodeError:
        # Handle case where file is empty or not valid JSON
        return []

def get_sorted_films(f, sorting_option):
    if sorting_option == 'year_latest':
        sorted_films = sorted(f, key=lambda film: int(film['year_released']) if film.get('year_released') else 0, reverse=True)
    elif sorting_option == 'year_earliest':
        sorted_films = sorted(f, key=lambda film: int(film['year_released']) if film.get('year_released') else 0)
    elif sorting_option == 'rating_highest':
        sorted_films = sorted(f, key=lambda film: int(film['details']['rating']) if film.get('details') and film['details'].get('rating') else 0, reverse=True)
    elif sorting_option == 'rating_lowest':
        sorted_films = sorted(f, key=lambda film: int(film['details']['rating']) if film.get('details') and film['details'].get('rating') else 0)
    elif sorting_option == 'longest':
        sorted_films = sorted(f, key=lambda film: film['details']['runtime'] if film.get('details') and film['details'].get('runtime') else 0, reverse=True)
    elif sorting_option == 'shortest':
        sorted_films = sorted(f, key=lambda film: film['details']['runtime'] if film.get('details') and film['details'].get('runtime') else 0)
    else:
        # Default sorting option
        sorted_films = f

    return sorted_films

def get_filtered_films(filter_options, similar_films):
    filtered_films = []
    for option in filter_options:
        if option.startswith("provider_"):
            provider_id = int(option.split("_")[1])
            for film in similar_films:
                if 'details' in film and 'providers' in film['details']:
                    if 'CA' in film['details']['providers']:
                        if 'free' in film['details']['providers']['CA']:
                            for provider in film['details']['providers']['CA']['free']:
                                if provider.get('provider_id') == provider_id and film not in filtered_films:
                                    filtered_films.append(film)
                        if 'flatrate' in film['details']['providers']['CA']:
                            for provider in film['details']['providers']['CA']['flatrate']:
                                if provider.get('provider_id') == provider_id and film not in filtered_films:
                                    filtered_films.append(film)
        if option.startswith("gen"):
            if filtered_films:
                data = filtered_films
            else:
                data = similar_films

            filtered_films = get_filtered_genre(data, option.split("_")[1])

        if option.startswith("run"):
            if filtered_films:
                data = filtered_films
            else:
                data = similar_films

            filtered_films = get_filtered_run(data, option.split("_")[1])

    # serialized_filtered_films = []
    # for i in filtered_films:
    #     f = serialize_film(i)
    #     serialized_filtered_films.append(f)

    return filtered_films


def serialize_film(film):
    serialized_film = {
        'title': film.title,
        'year_released': film.year_released,
        'letterboxd_uri': film.letterboxd_uri,
        'id': film.id,
        'details': {
            'genres': [genre for genre in film.details.genres],
            'production_countries': [country for country in film.details.production_countries],
            'runtime': film.details.runtime,
            'cast': [{
                'id': person.id,
                'name': person.name,
                'job': person.job,
                'character': person.character,
                'image': person.image
            } for person in film.details.cast],
            'crew': [{
                'id': person.id,
                'name': person.name,
                'job': person.job,
                'image': person.image
            } for person in film.details.crew],
            'image_url': film.details.image_url,
            'rating': film.details.rating,
            'user_rating': film.details.user_rating,
            'providers': film.details.providers,
            'still_img': film.details.still_img
        }
    }

    return serialized_film

def get_filtered_run(data, run):
    if run == "90":
        run_val = 90
        filtered_films = [film for film in data if 'details' in film and 'runtime' in film['details'] and run_val >= film['details']['runtime']]
    elif run == "120":
        run_val = 120
        filtered_films = [film for film in data if 'details' in film and 'runtime' in film['details'] and run_val >= film['details']['runtime']]
    elif run == "120+":
        run_val = 120
        filtered_films = [film for film in data if 'details' in film and 'runtime' in film['details'] and run_val <= film['details']['runtime']]
    else:
        filtered_films = []

    return filtered_films


def get_filtered_genre(data, genre):
    filtered_films = [film for film in data if 'details' in film and 'genres' in film['details'] and genre in film['details']['genres']]
    return filtered_films


if __name__ == '__main__':
    app.run(debug=True)
