from flask import Flask, request, redirect, session, jsonify
from flask_cors import CORS
import json
import os
import pandas as pd
import requests
import base64
from urllib.parse import urlencode
import string
import random
from dotenv import load_dotenv
import spotipy 
from spotipy import Spotify
from spotify_client import SpotifyClient
from rec_engine import RecEngine
from genre_class import GenreClassifier
from datetime import datetime, timedelta
import pandas as pd
import mysql.connector
from dotenv import load_dotenv
import os
from sql_work import SQLWork
from session_store import SessionStore

import random
from sklearn.metrics.pairwise import cosine_similarity
import time


# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False # Prevent jsonify from sorting keys in dict - Fix to top_ratios genre reordering

CORS(app, supports_credentials=True, origins="http://localhost:3000")


app.secret_key = os.getenv('FLASK_SECRET_KEY')

sql_work = SQLWork()
session_store = SessionStore()
# Initialize Genre Class Model
gc = GenreClassifier()
class_items = gc.load_model()

# Generate a random state string
def generate_random_string(length=16):
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for i in range(length))


@app.route('/auth/login')
def auth_login():
    print("Login route reached")
    scope = "streaming user-read-email user-read-private user-follow-read playlist-read-private playlist-read-collaborative user-read-recently-played user-library-read user-top-read"
    state = generate_random_string()
    params = {
        'response_type': 'code',
        'client_id': os.getenv('SPOTIFY_CLIENT_ID'),
        'scope': scope,
        'redirect_uri': 'http://localhost:3000/auth/callback', #5000 for production, 3000 for dev
        'state': state
    }
    url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    return redirect(url)

@app.route('/auth/callback')
def auth_callback():
    print("Callback route reached")
    code = request.args.get('code')
    state = request.args.get('state')
    # print(code, state)

    if not code:
        return "Error: No code in request", 400
    # Exchange code for token
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

    # Authorization header
    client_creds = f"{client_id}:{client_secret}"
    client_creds_b64 = base64.b64encode(client_creds.encode()).decode()

    auth_header = {
        'Authorization': f"Basic {client_creds_b64}",
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    auth_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://localhost:3000/auth/callback', #5000 for production, 3000 for dev
    }
    response = requests.post('https://accounts.spotify.com/api/token', data=auth_data, headers=auth_header)
    print(f"Token exchange response: {response.status_code}, {response.text}")
    if response.status_code == 200:
        token_info = response.json()
        session['access_token'] = token_info.get('access_token')
        session['refresh_token'] = token_info.get('refresh_token')
        session['token_expires'] = datetime.now().timestamp() + token_info.get('expires_in')

        start_time = time.time()
        
        sp = SpotifyClient(Spotify(auth=session.get('access_token')))
        unique_id, display_name = sql_work.get_user_data(sp)
        session['unique_id'] = unique_id
        print(unique_id, "stored in session")
        session['display_name'] = display_name

        re = RecEngine(sp, unique_id, sql_work)

        # Re-evaluate if this needs to be recalculated each time
        # Check from SQL
        user_top_tracks, user_top_artists = check_user_top_data_session(unique_id, re)

        print("Login time:", time.time() - start_time)  
       
        # Redirecting or handling logic here
        return redirect('http://localhost:3000/')
    else:
        return "Error in token exchange", response.status_code

def is_token_expired():
    return datetime.now().timestamp() > session.get('token_expires', 0)
        
@app.route('/auth/token')
def get_token():
    access_token = session.get('access_token')
    refresh_token = session.get('refresh_token')
    token_expires = session.get('token_expires')
    token_realexpire = session.get('token_realexpire')
    if access_token:
        return jsonify({'access_token': access_token, 
                        'refresh_token': refresh_token,
                        'token_expires': token_expires})
    else:
        return jsonify({'error': 'No token available'}), 401

@app.route('/auth/logout')
def logout():
    print("Logout route reached")
    session_store.remove_user_data(session.get('unique_id'))
    print("User data removed from session store")
    # session_store.clear_user_cache(session.get('unique_id'))
    # print("User cache cleared")
    session.clear()
    response = jsonify({"message": "Logout successful"})
    response.status_code = 200
    print("Logout response:", response)
    return response

def refresh_token():
    if 'refresh_token' not in session:
        return False
    print("-> app.py:refresh_token()")
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

    # Authorization header
    client_creds = f"{client_id}:{client_secret}"
    client_creds_b64 = base64.b64encode(client_creds.encode()).decode()

    auth_header = {
        'Authorization': f"Basic {client_creds_b64}",
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    auth_data = {
        'grant_type': 'refresh_token',
        'refresh_token': session['refresh_token']
    }

    response = requests.post('https://accounts.spotify.com/api/token', data=auth_data, headers=auth_header)
    if response.status_code == 200:
        new_token_info = response.json()
        session['access_token'] = new_token_info.get('access_token')
        session['token_expires'] = datetime.now().timestamp() + new_token_info.get('expires_in')
        sp = SpotifyClient(Spotify(auth=session.get('access_token')))
        unique_id, display_name = sql_work.get_user_data(sp)
        session['unique_id'] = unique_id
        session['display_name'] = display_name

        recache_threshold = timedelta(days=1)
        last_cached_str = session.get('top_last_cached')

        if last_cached_str is None:
            last_cached = None
        else:
            last_cached = datetime.fromisoformat(last_cached_str)
        
        if last_cached is None or datetime.now() - last_cached > recache_threshold:

            re = RecEngine(sp, unique_id, sql_work)

            user_top_tracks, user_top_artists = check_user_top_data_session(unique_id, re)

        return True
    else:
        return False



def check_user_top_data_session(unique_id, re):
    redis_key_top_tracks = f"{unique_id}:top_tracks"
    redis_key_top_artists = f"{unique_id}:top_artists"
    
    user_top_tracks = session_store.get_data(redis_key_top_tracks)
    user_top_artists = session_store.get_data(redis_key_top_artists)
    if user_top_tracks:
        print("User top tracks found")
        ##Add recache function here
    else:
        print("User top tracks not found")
        user_top_tracks = re.get_user_top_tracks()
        session_store.set_user_top_data(redis_key_top_tracks, user_top_tracks)
        print("User top tracks saved")
    if user_top_artists:
        print("User top artists found")
    else:
        print("User top artists not found")
        user_top_artists = re.get_user_top_artists()
        session_store.set_user_top_data(redis_key_top_artists, user_top_artists)
        print("User top artists saved")
    return user_top_tracks, user_top_artists


# Append Data to rec_dataset
def append_to_dataset(data, choice):
    session['append_counter'] = session.get('append_counter', 0) + 1
    print("Append counter:", session['append_counter'])

    new_data = data.copy()
    if choice == 'track':
        new_data.drop('release_date', axis=1, inplace=True)  # Remove 'release_date' column if choice is 'track'
    elif choice == 'playlist':
        new_data.drop('date_added', axis=1, inplace=True)  # Remo   ve 'date_added' column if choice is 'playlist'
    new_data.rename(columns={'artist': 'artists', 'name': 'track_name', 'id': 'track_id'}, inplace=True)  # Rename columns
    append_counter = session['append_counter']
    start_time = time.time()
    append = sql_work.append_tracks(new_data, append_counter)
    print("Appended tracks in %s seconds", (time.time() - start_time))
    if append:
        session['append_counter'] = 0 

def get_playlist_data_session(unique_id,link):
    if session.get('last_search') == link:
        redis_key_playlist = f"{unique_id}:{link}:playlist_vector"
        p_vector = session_store.get_data(redis_key_playlist)
        p_features = session.get('p_features', {})
        top_genres = session.get('top_genres')
        top_ratios = session.get('top_ratios')
        return p_vector, p_features, top_genres, top_ratios
    return None

def get_track_data_session(unique_id, link):
    if session.get('last_search') == link:
        redis_key_track = f"{unique_id}:{link}:track_vector"
        t_vector = session_store.get_data(redis_key_track)
        t_features = session.get('t_features', {})
        return t_vector, t_features
    return None

def save_playlist_data_session(unique_id, playlist,  p_features, link, re, sp):
    p_vector = re.playlist_vector(playlist) # Get playlist vector
    top_genres, top_ratios = re.get_top_genres(p_vector) # Get top genres

    # Save playlist data to session
    redis_key_playlist = f"{unique_id}:{link}:playlist_vector"
    session_store.set_vector(redis_key_playlist, p_vector)
    session['top_genres'] = top_genres # To send as names to front end 
    session['top_ratios'] = top_ratios
    session['last_search'] = link 
    session['p_features'] = p_features

    print('Playlist data saved to session')
    return p_vector, p_features, top_genres, top_ratios,

def save_track_data_session(unique_id, track, t_features, link, re, sp):
    t_vector = re.track_vector(track) # Get track vector
    
    # Save track data to session
    redis_key_track = f"{unique_id}:{link}:track_vector"
    session_store.set_vector(redis_key_track, t_vector)
    session['t_features'] = t_features 
    session['last_search'] = link
    return t_vector, t_features

@app.route('/recommend', methods=['GET'])
def recommend():

    start_finish_time = time.time()
    # Check if the access token is expired and refresh if necessary
    if is_token_expired():
        if not refresh_token():
            return redirect('/auth/login')

    sp = SpotifyClient(Spotify(auth=session.get('access_token'))) # Initialize SpotifyClient
    unique_id = session.get('unique_id')
    re = RecEngine(sp, unique_id, sql_work)

    link = request.args.get('link')
    if not link:
        return jsonify({'error': 'No link provided'}), 400 # Cannot process request

    if '/' in link:
        # Extract the type and ID from the link
        type_id = link.split('/')[3]
        link = link.split('/')[-1].split('?')[0]
    else:
        type_id = 'playlist'

    rec_redis_key = f'{unique_id}:{link}:{type_id}'
    # print(rec_redis_key)
    
    user_top_tracks, user_top_artists = check_user_top_data_session(unique_id, re)

    if type_id == 'playlist':
        # Check if playlist data exists in session
        playlist_data = get_playlist_data_session(unique_id, link)
        if playlist_data:
            print('Playlist data exists')
            p_vector, p_features, top_genres, top_ratios = playlist_data
            stored_recommendations = session_store.get_data(rec_redis_key)
            track_ids = stored_recommendations['track_ids']
            previously_recommended = stored_recommendations['recommended_ids']
            # re = RecEngine(sp, unique_id, sql_work)
        else:
            print('Saving playlist data to session')
            previously_recommended = []
            # re = RecEngine(sp, unique_id, sql_work)
            playlist, p_features = sp.playlist_base_features(link)
            playlist = sp.predict(playlist, type_id, class_items)
            playlist.to_csv('playlist.csv', index=False)
            track_ids = set(playlist['id'])
            
            p_features.update({
                'num_tracks': len(track_ids),
                'total_duration_ms': int(playlist['duration_ms'].sum())
            })

            # append_to_dataset(playlist, type_id) # Append Playlist songs to dataset
            p_vector, p_features, top_genres, top_ratios = save_playlist_data_session(unique_id, playlist, p_features, link,  re, sp) # Save Playlist data to session
            print(top_ratios)
        
        recommended_ids = re.recommend_by_playlist(rec_dataset, p_vector, track_ids, user_top_tracks, user_top_artists, class_items, top_genres, top_ratios, previously_recommended)

    elif type_id == 'track':
        # Check if track data exists in session
        track_data = get_track_data_session(unique_id, link)
        if track_data:
            print('Track data exists')
            t_vector, t_features = track_data
            stored_recommendations = session_store.get_data(rec_redis_key)
            track_ids = stored_recommendations['track_ids']
            previously_recommended = stored_recommendations['recommended_ids']
        else:
            print('Saving track data to session')
            previously_recommended = []
            
            track, t_features = sp.track_base_features(link) 
            track.to_csv('track.csv', index=False)
            track = sp.predict(track, type_id, class_items)
            track_ids = [link]

            t_features.update({ 
                'total_duration_ms': int(track['duration_ms']),
            })
            
            # append_to_dataset(track, type_id) # Append Track to dataset
            
            t_vector, t_features = save_track_data_session(unique_id, track, t_features, link, re, sp) # Save Track data to session
               
        # Get recommendations
        recommended_ids = re.recommend_by_track(rec_dataset, t_vector, track_ids, user_top_tracks, class_items, previously_recommended)

    # Update recommended songs in session
    updated_recommendations = set(previously_recommended).union(set(recommended_ids))
    print("Length of updated_recommendations:", len(updated_recommendations))
    session_store.set_prev_rec(rec_redis_key, list(track_ids), list(updated_recommendations)) # Update prev rec for user
    session_store.set_random_recs(list(updated_recommendations)) # Update random recs app wide
    memory_usage = session_store.get_memory_usage(rec_redis_key)
    print("Memory usage:", memory_usage, "bytes") 
    stored_recommendations = session_store.get_data(rec_redis_key)
    if stored_recommendations:
        track_ids = stored_recommendations['track_ids']
        prev_rec = stored_recommendations['recommended_ids']
        duplicate_strings = len(set(prev_rec)) != len(prev_rec)
        prev_rec_df = pd.DataFrame(prev_rec, columns=['prev_recommended_ids'])
        print("Duplicate strings in recommended_ids:", duplicate_strings)
        print("Length of track_ids:", len(track_ids))
        print("Length of recommended_ids:", len(prev_rec))
    else:
        print("Stored recommendations not found")
        
    start_time = time.time()    
    session_store.update_total_recs(len(recommended_ids))


    print("Time taken to update user recommendation count:", time.time() - start_time)
    print("Time taken to get recommendations:", time.time() - start_finish_time)


    if type_id == 'playlist':
        return jsonify({
            'p_features': p_features,
            'top_genres': top_genres,
            'recommended_ids': recommended_ids,
            'id': link,
        })
    elif type_id == 'track':
        return jsonify({
            't_features': t_features,
            
            'recommended_ids': recommended_ids,
            'id': link
        })

@app.route('/search', methods=['GET'])
def autocomplete_playlist():
    unique_id = session.get('unique_id')
    playlists = sql_work.get_unique_user_playlist(unique_id)
    return jsonify(playlists)


@app.route('/user', methods=['GET'])
def get_user_data():
    unique_id = session.get('unique_id')
    display_name = session.get('display_name')
    return jsonify({'unique_id': unique_id, 'display_name': display_name})

@app.route('/favorited', methods=['POST'])
def save_favorited():
    data = request.get_json()
    favorited_tracks = data.get('favoritedTracks', [])
    recommendation_id = data.get('recommendationID')
    if favorited_tracks:
        unique_id = session.get('unique_id')
        print(unique_id)
        sql_work.add_liked_tracks(unique_id, recommendation_id, favorited_tracks)
        return jsonify({'message': 'Favorited tracks saved successfully'})
    else:
        return jsonify({'message': 'No favorited tracks provided'})

@app.route('/total-recommendations', methods=['GET'])
def get_total_recommendations():
    total_recommendations, hourly_recs = session_store.get_total_recs()
    print("Total recommendations:", total_recommendations, "Hourly recommendations:", hourly_recs)
    return jsonify([total_recommendations, hourly_recs])

@app.route('/random-recommendations', methods=['GET'])
def get_random_recommendations():
    random_recs = session_store.get_random_recs()
    return jsonify(random_recs)



@app.route('/test') ### Keep for testing new features
def test():
    unique_id: str = session.get('unique_id')
    access_token: str = session.get('access_token')

    # # Create Spotify client and RecEngine instance
    sp = SpotifyClient(Spotify(auth=access_token))
    re = RecEngine(sp, unique_id, sql_work)



    link = input("Enter a playlist link: ")
    # if not link:
    #     break
    link = link.split('/')[-1].split('?')[0]
    
    # track = sp.sp.track(link)
    track, t_features  = sp.track_base_features(link)
    track = sp.predict(track, 'track', class_items)
    print(t_features)
   
    return jsonify(
        # {'name': name, 'image_300x300': image_300x300, 'artist': artist, 'artist_url': artist_url, 'release_date': release_date, 'popularity': popularity, 'id': link}
        track.to_dict(orient='records')
    )






    #     playlist = sp.predict(link, 'playlist', class_items)
    #     top_genres = playlist['track_genre'].value_counts().head(3).index.tolist()
    #     print("Top three genres:", top_genres)
    #     playlist.to_csv('playlist.csv')

    # session_store.update_total_recs(30)
    # action = input("Enter: 1. Delete keys, 2. Get Random Recommendations")

    # if (action == '1'): 
    #     session_store.delete_keys()


    #     if session_store.redis.exists(session_store._get_sample_taken_key()):
    #         return jsonify({'message': 'Sample already taken, no random recs saved'})
    #     return jsonify(' Sample not taken, random recs saved') 

    # elif (action == '2'):
    #     total_recs, hourly_recs = session_store.get_total_recs()

    #     print("Total recommendations:", total_recs, "Hourly recommendations:", hourly_recs)

    #     random_recs = session_store.get_random_recs()

    # session_store.clear_all()
    # session_store.set_total_recs(8299)

    # print("Total recommendations:", total, "Hourly recommendations:", hourly)
    # recently_played = sp.sp.current_user_top_artists(20,0, 'long_term')
    # return jsonify(playlist_json)




if __name__ == '__main__':
    global rec_dataset
    # sql_work.connect_sql()
    rec_dataset = sql_work.get_dataset()
    app.run(debug=True, port=5000)
