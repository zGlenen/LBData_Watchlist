class Film():
    def __init__(self,title,year_released,letterboxd_uri,id,details):
        
        self.title = title
        self.year_released = year_released
        self.letterboxd_uri = letterboxd_uri
        self.id = id
        self.details = details

class Person:
    def __init__(self,id,name,job=None,character=None,p_image=None):
        self.id = id
        self.name = name
        self.job = job
        self.character = character
        self.image = p_image


class FilmDetails:
    def __init__(self,genres,production_countries,runtime,cast,crew,image_url,rating,user_rating,providers = None, still_img = None):
        self.genres = genres
        self.production_countries = production_countries
        self.runtime = runtime
        self.cast = cast
        self.crew = crew
        self.image_url = image_url
        self.rating = rating
        self.user_rating = user_rating
        self.providers = providers
        self.still_img = still_img
