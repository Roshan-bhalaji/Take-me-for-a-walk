import json
import os
import streamlit as st
from streamlit import session_state
from dotenv import load_dotenv
import smtplib
import random
import string
import re
import datetime
import requests
import hashlib
import googlemaps
from geopy.geocoders import Nominatim
import networkx as nx
from networkx.algorithms.shortest_paths.weighted import dijkstra_path
import folium
from streamlit_folium import folium_static
import polyline
from streamlit_js_eval import get_geolocation
from time import sleep
import streamlit.components.v1 as components

session_state = st.session_state
# if "user_index" not in st.session_state:
#     st.session_state["user_index"] = 0

if "lat" not in st.session_state:
    st.session_state["latitude"] = None
if "lon" not in st.session_state:
    st.session_state["longitude"] = None
if "LOCATION" not in st.session_state:
    st.session_state["LOCATION"] = None
if "recommendations" not in st.session_state:
    st.session_state["recommendations"] = None
load_dotenv()
LOCATION = session_state["LOCATION"]
SENDER_MAIL_ID = os.getenv("SENDER_MAIL_ID")
APP_PASSWORD = os.getenv("APP_PASSWORD")
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

st.set_page_config(
    page_title="Take me for a walk",
    page_icon="favicon.ico",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Get Help": "https://www.extremelycoolapp.com/help",
        "Report a bug": "https://www.extremelycoolapp.com/bug",
        "About": "# This is a header. This is an *extremely* cool app!",
    },
)

gmaps = googlemaps.Client(key=API_KEY)

# Initialize the Nominatim geocoder
geolocator = Nominatim(user_agent="my_app")

def calculate_time_range(max_time, percentage=0.25):
    range_value = max_time * percentage
    min_time = max_time - range_value
    max_time = max_time + range_value
    return min_time, max_time

def calculate_change_in_evaluation(difficulty):
    if difficulty == -5:
        return -5000 * 0.3048
    elif difficulty == -4:
        return -3000 * 0.3048
    elif difficulty == -3:
        return -2000 * 0.3048
    elif difficulty == -2:
        return -1000 * 0.3048
    elif difficulty == -1:
        return -500 * 0.3048
    elif difficulty == 0:
        return 0
    elif difficulty == 1:
        return 500 * 0.3048
    elif difficulty == 2:
        return 1000 * 0.3048
    elif difficulty == 3:
        return 2000 * 0.3048
    elif difficulty == 4:
        return 3000 * 0.3048
    elif difficulty == 5:
        return 5000 * 0.3048

def get_elevation(location):
    lat, lng = location
    elevation_url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={lat},{lng}&key={API_KEY}"
    response = requests.get(elevation_url).json()
    return response["results"][0]["elevation"] if response["results"] else 0

def get_routes(origin_lat, origin_lon, destination_lat, destination_lon, mode="walking"):
    try:
        base_url = "https://maps.googleapis.com/maps/api/directions/json"
        origin = f"{origin_lat},{origin_lon}"
        destination = f"{destination_lat},{destination_lon}"
        
        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "alternatives": "true",
            "key": API_KEY
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Error in request: {response.status_code}")
        
        data = response.json()
        
        if data["status"] != "OK":
            raise Exception(f"Error in response: {data['status']}")
        
        # Extract all routes
        routes = data["routes"]
        
        # Store travel times and routes
        all_routes_info = []
        for route in routes:
            travel_time_seconds = route["legs"][0]["duration"]["value"]
            travel_time_minutes = travel_time_seconds / 60
            all_routes_info.append({
                "route": route,
                "travel_time_minutes": travel_time_minutes
            })
        
        return all_routes_info
    except googlemaps.exceptions.ApiError:
        return []

def get_city_name(lat, lon):
    """Get city name from latitude and longitude using Google Maps Geocoding API."""
    url = f'https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={API_KEY}'
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json().get('results', [])
        if results:
            for component in results[0]['address_components']:
                if 'locality' in component['types']:
                    return component['long_name']
    return "Unknown"

def display_route(route_data, landmarks, difficulty):
    # Extract start and end coordinates
    start_location = route_data[0]['route']['legs'][0]['start_location']
    end_location = route_data[-1]['route']['legs'][0]['end_location']
    
    # Create a map centered on the start location
    m = folium.Map(location=[start_location['lat'], start_location['lng']], zoom_start=15)
    
    # Add start and end markers
    folium.Marker(
        [start_location['lat'], start_location['lng']],
        popup='Start',
        icon=folium.Icon(color='green', icon='play')
    ).add_to(m)
    
    folium.Marker(
        [end_location['lat'], end_location['lng']],
        popup='End',
        icon=folium.Icon(color='red', icon='stop')
    ).add_to(m)
    
    # Decode and add the route polyline
    for route in route_data:
        route_points = polyline.decode(route['route']['overview_polyline']['points'])
        folium.PolyLine(route_points, weight=5, opacity=0.8, color='blue').add_to(m)
    
    # Add step markers
    for i, route in enumerate(route_data):
        for step in route['route']['legs'][0]['steps']:
            folium.Marker(
                [step['start_location']['lat'], step['start_location']['lng']],
                popup=f"Step {i+1}",
                icon=folium.Icon(color='orange', icon='info-sign')
            ).add_to(m)
    
    # Display the map in Streamlit
    st.write("Route Map")
    folium_static(m)
    
    # Display route information
    st.subheader("Route Information:")
    st.info(f"Distance: {route_data[-1]['route']['legs'][0]['distance']['text']}")
    st.info(f"Duration: {route_data[-1]['route']['legs'][0]['duration']['text']}")
    st.info(f"Start Address: {route_data[0]['route']['legs'][0]['start_address']}")
    st.info(f"End Address: {route_data[-1]['route']['legs'][0]['end_address']}")
    st.info(f"Path Difficulty: {difficulty}")


def create_graph_and_find_optimal_route(routes, max_time, weight_time, weight_elevation):
    G = nx.DiGraph()

    for route in routes:
        leg = route["route"]["legs"][0]
        total_duration = leg["duration"]["value"]
        if total_duration > max_time * 60:
            continue
        for step in leg["steps"]:
            start_location = (step["start_location"]["lat"], step["start_location"]["lng"])
            end_location = (step["end_location"]["lat"], step["end_location"]["lng"])
            distance = step["distance"]["value"]
            duration = step["duration"]["value"]
            elevation = get_elevation(end_location)
            landmarks_count = sum(1 for landmark in ["Park", "Museum", "Restaurant", "Cafe", "Hotel"] if landmark in step["html_instructions"])
            effort = (weight_time * duration) + (weight_elevation * elevation) - (landmarks_count * 1000)
            G.add_edge(start_location, end_location, weight=effort, duration=duration, elevation=elevation, landmarks=landmarks_count)

    start_node = (
        routes[0]["route"]["legs"][0]["start_location"]["lat"],
        routes[0]["route"]["legs"][0]["start_location"]["lng"],
    )
    end_node = (
        routes[-1]["route"]["legs"][0]["end_location"]["lat"],
        routes[-1]["route"]["legs"][0]["end_location"]["lng"],
    )

    if start_node not in G or end_node not in G:
        st.error(f"Start or end node not found in the graph")
        return []

    shortest_path = dijkstra_path(G, source=start_node, target=end_node, weight="weight")

    optimal_route = []
    for node in shortest_path:
        for route in routes:
            for step in route["route"]["legs"][0]["steps"]:
                if (step["start_location"]["lat"], step["start_location"]["lng"]) == node:
                    route["landmarks_count"] = sum(1 for landmark in ["Park", "Museum", "Restaurant", "Cafe", "Hotel"] if landmark in step["html_instructions"])
                    optimal_route.append(route)
                    break

    return optimal_route

def get_all_nearby_places(radius=500000, place_type="point_of_interest"):
    gmaps = googlemaps.Client(key=API_KEY)
    origin_lat = session_state["LOCATION"]["latitude"]
    origin_lon = session_state["LOCATION"]["longitude"]
    all_results = []

    # Initial request
    nearby_places = gmaps.places_nearby(
        location=(origin_lat, origin_lon),
        radius=radius,
        type=place_type
    )
    all_results.extend(nearby_places['results'])

    # Check for more pages
    while 'next_page_token' in nearby_places:
        next_page_token = nearby_places['next_page_token']
        sleep(2)
        nearby_places = gmaps.places_nearby(
            location=(origin_lat, origin_lon),
            radius=radius,
            type=place_type,
            page_token=next_page_token
        )
        all_results.extend(nearby_places['results'])
    return all_results

def minimum_time(origin_lat, origin_lon, destination_lat, destination_lon, mode="walking"):
    base_url = "https://maps.googleapis.com/maps/api/directions/json"
    origin = f"{origin_lat},{origin_lon}"
    destination = f"{destination_lat},{destination_lon}"
    
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "key": API_KEY
    }
    
    response = requests.get(base_url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Error in request: {response.status_code}")
    
    data = response.json()
    
    if data["status"] != "OK":
        raise Exception(f"Error in response: {data['status']}")
    
    # Extract the travel time from the response
    travel_time_seconds = data["routes"][0]["legs"][0]["duration"]["value"]
    travel_time_minutes = travel_time_seconds / 60
    
    return travel_time_minutes

def search_nearby_places(location, radius, types):
    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    
    params = {
        "location": location,
        "radius": radius,
        "type": types,
        "key": API_KEY
    }
    
    response = requests.get(base_url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Error in request: {response.status_code}")
    
    data = response.json()
    
    if data["status"] != "OK":
        return []
    
    places = data["results"]
    place_names = [place["name"] for place in places]
    return place_names

def get_recommendations(preferences):
    try:
        origin_lat = session_state["LOCATION"]["latitude"]
        origin_lon = session_state["LOCATION"]["longitude"]
        with st.spinner("Finding nearby places..."):
            nearby_places = get_all_nearby_places()
        mode = preferences["mode"]
        max_time = preferences["max_time"]
        min_time, max_time = calculate_time_range(max_time, percentage=0.25)
        change_in_elevation = calculate_change_in_evaluation(preferences["change_in_elevation"])
        avoids = preferences["avoid"]
        valid_places = []
        with st.progress(0, text="Finding recommendations..."):
            for i, place in enumerate(nearby_places):
                destination_lat = place["geometry"]["location"]["lat"]
                destination_lon = place["geometry"]["location"]["lng"]
                total_duration = minimum_time(origin_lat, origin_lon, destination_lat, destination_lon, mode=mode)
                progress_percentage = int((i / len(nearby_places)) * 100)
                st.progress(progress_percentage, text=f"Finding recommendations... {progress_percentage}%")
                if min_time <= total_duration <= max_time:
                    place["total_duration"] = total_duration
                    valid_places.append(place)

        st.progress(100, text="Finding recommendations...")
        print(f"Valid places: {valid_places}")

        # If no valid places found, show a message and return
        if not valid_places:
            st.error("No places found within the specified time limit.")
            return []

        recommendations = {}
        for place in valid_places:
            destination_lat = place["geometry"]["location"]["lat"]
            destination_lon = place["geometry"]["location"]["lng"]
            routes = get_routes(origin_lat, origin_lon, destination_lat, destination_lon, mode=mode)
            optimal_route = create_graph_and_find_optimal_route(routes, max_time, weight_time=1, weight_elevation=1)
            if optimal_route:
                recommendations[place["name"]] = optimal_route

        # print(f"Recommendations: {recommendations}")

        # Display recommendations
        if recommendations:
            st.success("Recommendations generated successfully!")
            session_state["recommendations"] = recommendations
            st.title(f"Top {min(10, len(recommendations))} Recommendations")
            for place, route in recommendations.items():
            #     st.subheader(place)
            #     st.info(f"Duration: {route[0]['route']['legs'][0]['duration']['text']}")
            #     st.info(f"Number of Landmarks: {route[0]['landmarks_count']}")
               display_route(route, ["Park", "Museum", "Restaurant", "Cafe", "Hotel"], preferences["change_in_elevation"])


        return recommendations
    except Exception as e:
        st.error(f"Error getting nearby places: {e}")
        return []


def render_dashboard():
   
    if LOCATION:
        st.subheader("User Location")
        st.info(f"Latitude: {LOCATION['latitude']}")
        st.info(f"Longitude: {LOCATION['longitude']}")
        st.info(f"City: {get_city_name(LOCATION['latitude'], LOCATION['longitude'])}")
        map_html = f'''
            <iframe
                width="600"
                height="450"
                style="border:0"
                loading="lazy"
                allowfullscreen
                src="https://www.google.com/maps/embed/v1/view?key={API_KEY}&center={float(LOCATION['latitude'])},{float(LOCATION['longitude'])}&zoom=18">
            </iframe>
            '''
        with st.expander("View Map"):
            components.html(map_html,width =1200, height=500)
    

def main(json_file_path="data.json"):
    page = st.sidebar.selectbox(
        "Go to",
        (
            "Dashboard",
            "Take me for a walk",
        ),
        key="page",
    )

    # if st.sidebar.button("Logout"):
    #     session_state["logged_in"] = False
    #     session_state["user_info"] = None
    #     st.success("You have been logged out successfully!")
    #     st.rerun()

    if page == "Dashboard":
        render_dashboard()

    else:
    
        st.title("Custom Route Visualization with Google Maps")
        landmarks = st.multiselect(
            "Landmarks", ["Park", "Museum", "Restaurant", "Cafe", "Hotel"]
        )
        mode = st.selectbox("Mode", ["walking", "driving"])
        max_time = st.number_input("Maximum Time (minutes)", min_value=1, value=20)
        change_in_elevation = st.slider(
            "Path difficulty",
            min_value=-5,
            max_value=5,
            value=1,
        )

        avoid_tolls = st.checkbox("Avoid Tolls")
        avoid_ferries = st.checkbox("Avoid Ferries")
        avoid_highways = st.checkbox("Avoid Highways")
        if st.button("Find Route"):
            preferences = {
                "landmarks": landmarks,
                "mode": mode,
                "max_time": max_time,
                "change_in_elevation": change_in_elevation,
                "avoid": {
                    "tolls": avoid_tolls,
                    "ferries": avoid_ferries,
                    "highways": avoid_highways,
                },
            }
            get_recommendations(preferences)
        if st.session_state["recommendations"]:
            recommendations = st.session_state["recommendations"]
            # st.title(f"Top {min(10, len(recommendations))} Recommendations")
            # for place, route in recommendations.items():
            #     # st.subheader(place)
            #     # st.info(f"Duration: {route[0]['route']['legs'][0]['duration']['text']}")
            #     # st.info(f"Number of Landmarks: {route[0]['landmarks_count']}")
            #     display_route(route, ["Park", "Museum", "Restaurant", "Cafe", "Hotel"])
            st.write("---")
        
if __name__ == "__main__":
    if "LOCATION" not in session_state or session_state["LOCATION"] is None:
        while session_state["LOCATION"] is None:
            session_state["LOCATION"] = get_geolocation()
            sleep(2)
        session_state["LOCATION"] = session_state["LOCATION"]["coords"]
        session_state["latitude"] = float(session_state["LOCATION"]["latitude"])
        session_state["longitude"] = float(session_state["LOCATION"]["longitude"])
    main()
