from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import requests
import datetime
import re

# Load environment variables
load_dotenv()

# Configure Google Gemini API
genai.configure(api_key=os.getenv("API_KEY"))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI", "sqlite:///geoguide.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User model for database
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    preferences = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'

# Itinerary model for storing generated itineraries
class Itinerary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    itinerary_data = db.Column(db.JSON, nullable=False)
    transportation_method = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship('User', backref=db.backref('itineraries', lazy=True))

# Create tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return redirect(url_for('signup'))
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        return redirect(url_for('preferences'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        # Gather preference data
        preferences = {
            'travel_style': request.form.get('travel_style'),
            'interests': request.form.getlist('interests'),
            'accessibility_needs': request.form.getlist('accessibility_needs'),
            'has_pets': request.form.get('has_pets') == 'yes',
            'preferred_environments': request.form.getlist('environments'),
            'budget_level': request.form.get('budget'),
            'activity_level': request.form.get('activity_level'),
            'dietary_restrictions': request.form.getlist('dietary_restrictions')
        }
        
        user.preferences = preferences
        db.session.commit()
        
        return redirect(url_for('dashboard'))
    
    return render_template('preferences.html', user=user)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Handle case where user hasn't set preferences yet
    if not user.preferences:
        return redirect(url_for('preferences'))
    
    # Get user's saved itineraries
    itineraries = Itinerary.query.filter_by(user_id=user.id).order_by(Itinerary.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', user=user, itineraries=itineraries)

# New route to handle geolocation API request
@app.route('/api/get_location_info', methods=['POST'])
def get_location_info():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if not latitude or not longitude:
        return jsonify({"error": "Latitude and longitude are required"}), 400
    
    try:
        # Use Geocoding API to get the location name
        # In a production app, you'd want to use a proper geocoding service with an API key
        # This is a placeholder - replace with an actual geocoding service API call
        location_name = get_location_name(latitude, longitude)
        
        # Get optimal transportation recommendations based on location
        transportation_options = recommend_transportation(latitude, longitude)
        
        # Get nearby points of interest
        nearby_pois = get_nearby_pois(latitude, longitude)
        
        return jsonify({
            "location_name": location_name,
            "coordinates": {"lat": latitude, "lng": longitude},
            "transportation_recommendations": transportation_options,
            "nearby_pois": nearby_pois
        })
    except Exception as e:
        print(f"Error in get_location_info: {e}")
        return jsonify({"error": str(e)}), 500

# Helper function to get location name from coordinates
def get_location_name(latitude, longitude):
    # In a production app, use a proper geocoding API
    # This is a placeholder implementation
    try:
        # Example using a free geocoding service (replace with your preferred service)
        response = requests.get(f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=18&addressdetails=1")
        data = response.json()
        
        # Extract city/town name
        address = data.get('address', {})
        location = address.get('city') or address.get('town') or address.get('village') or data.get('display_name', 'Unknown location')
        
        return location
    except Exception as e:
        print(f"Error getting location name: {e}")
        return "Unknown location"

# Helper function to recommend transportation options
def recommend_transportation(latitude, longitude):
    # This function would ideally use local transportation APIs
    # For now, we'll use a simplified implementation
    
    # Call Gemini to get transportation recommendations
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = f"""
    Based on the geographic coordinates (latitude: {latitude}, longitude: {longitude}),
    recommend optimal transportation options for a tourist. 
    
    Consider:
    - Typical transportation infrastructure in this area
    - Public transit availability
    - Walking/biking feasibility
    - Local customs and norms
    
    Return the response as a JSON list with this structure:
    [
        {{
            "method": "walking",
            "name": "Walking",
            "suitability": "High/Medium/Low",
            "reasons": ["reason 1", "reason 2"],
            "booking_info": null
        }},
        {{
            "method": "public_transit",
            "name": "Public Transit",
            "suitability": "High/Medium/Low",
            "reasons": ["reason 1", "reason 2"],
            "booking_info": {{
                "name": "Local Transit App",
                "url": "https://example.com"
            }}
        }}
    ]
    
    Include options for: walking, public_transit, driving, bicycle, railway, airways, bus.
    For methods that require booking, include relevant booking_info.
    Make sure your response is valid JSON with no additional text.
    """
    
    try:
        response = model.generate_content(prompt)
        
        # Try to parse the response as JSON
        try:
            transportation_options = json.loads(response.text)
            return transportation_options
        except json.JSONDecodeError:
            # Try to extract JSON from code blocks or response
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response.text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                return json.loads(json_str)
            
            # Final attempt to extract JSON
            json_match = re.search(r'(\[.*\])', response.text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                return json.loads(json_str)
            
            # Return default options if all parsing fails
            return get_default_transportation_options()
            
    except Exception as e:
        print(f"Error recommending transportation: {e}")
        return get_default_transportation_options()

# Default transportation options
def get_default_transportation_options():
    return [
        {
            "method": "walking",
            "name": "Walking",
            "suitability": "Medium",
            "reasons": ["Good for short distances", "Allows exploration of local area"],
            "booking_info": None
        },
        {
            "method": "public_transit",
            "name": "Public Transit",
            "suitability": "Medium",
            "reasons": ["May be available in the area", "Cost-effective option"],
            "booking_info": {
                "name": "Google Maps",
                "url": "https://maps.google.com"
            }
        },
        {
            "method": "driving",
            "name": "Driving",
            "suitability": "Medium",
            "reasons": ["Flexible transportation option", "Good for covering larger distances"],
            "booking_info": {
                "name": "Car Rental",
                "url": "https://www.rentalcars.com"
            }
        }
    ]

# Helper function to get nearby POIs
def get_nearby_pois(latitude, longitude):
    # This function would ideally use an API like Google Places
    # For now, we'll use Gemini to simulate POI recommendations
    
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = f"""
    Based on the geographic coordinates (latitude: {latitude}, longitude: {longitude}),
    recommend 5 nearby points of interest for a tourist.
    
    Return the response as a JSON list with this structure:
    [
        {{
            "name": "POI Name",
            "type": "Museum/Park/Restaurant/etc",
            "description": "Brief description",
            "estimated_distance": "X km/miles"
        }}
    ]
    
    Make sure your response is valid JSON with no additional text.
    """
    
    try:
        response = model.generate_content(prompt)
        
        # Try to parse the response as JSON
        try:
            nearby_pois = json.loads(response.text)
            return nearby_pois
        except json.JSONDecodeError:
            # Try to extract JSON from code blocks or response
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response.text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                return json.loads(json_str)
            
            # Final attempt to extract JSON
            json_match = re.search(r'(\[.*\])', response.text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                return json.loads(json_str)
            
            # Return default options if all parsing fails
            return get_default_nearby_pois()
            
    except Exception as e:
        print(f"Error getting nearby POIs: {e}")
        return get_default_nearby_pois()

# Default nearby POIs
def get_default_nearby_pois():
    return [
        {
            "name": "Local Museum",
            "type": "Museum",
            "description": "Explore the local history and culture",
            "estimated_distance": "1.5 km"
        },
        {
            "name": "Central Park",
            "type": "Park",
            "description": "Relax in this beautiful green space",
            "estimated_distance": "0.8 km"
        },
        {
            "name": "Popular Restaurant",
            "type": "Restaurant",
            "description": "Try local cuisine at this highly-rated eatery",
            "estimated_distance": "1.2 km"
        }
    ]

@app.route('/current_location')
def current_location():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Handle case where user hasn't set preferences yet
    if not user.preferences:
        return redirect(url_for('preferences'))
    
    return render_template('current_location.html', user=user)

@app.route('/recommend', methods=['GET', 'POST'])
def recommend_pois():
    if 'user_id' not in session:
        flash('Please login first')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Get location data from form
        location = request.form.get('location')
        radius = request.form.get('radius', 5)  # Default 5km radius
        transportation = request.form.get('transportation', 'walking')  # New parameter
        
        if not location:
            flash('Please provide a location')
            return redirect(url_for('dashboard'))
        
        try:
            # Store transportation in session for later use
            session['transportation'] = transportation
            
            # Get personalized recommendations using Gemini
            recommendations = get_gemini_recommendations(user.preferences, location, radius, transportation)
            
            # Make sure recommendations is a dictionary with a "recommendations" key
            if not isinstance(recommendations, dict):
                recommendations = {"recommendations": []}
            elif "recommendations" not in recommendations:
                recommendations = {"recommendations": []}
                
            # Debug print
            print(f"Generated recommendations: {recommendations}")
                
            return render_template('recommendations.html', 
                                  recommendations=recommendations, 
                                  location=location,
                                  transportation=transportation)
        except Exception as e:
            print(f"Error in recommend_pois route: {e}")
            flash(f"An error occurred: {str(e)}")
            return redirect(url_for('dashboard'))
    
    # For GET requests, show the recommendation form
    transportation_options = [
        {"id": "walking", "name": "Walking"},
        {"id": "public_transit", "name": "Public Transit"},
        {"id": "driving", "name": "Driving"},
        {"id": "bicycle", "name": "Bicycle"},
        {"id": "railway", "name": "Railway"},
        {"id": "airways", "name": "Airways"},
        {"id": "bus", "name": "Bus"}
    ]
    
    return render_template('recommend_form.html', 
                          user=user, 
                          transportation_options=transportation_options)

@app.route('/plan_itinerary', methods=['POST'])
def plan_itinerary():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Get planning parameters
    location = request.form.get('location')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    poi_list = request.form.getlist('selected_pois')
    transportation = request.form.get('transportation', session.get('transportation', 'walking'))
    
    # Generate itinerary using Gemini
    itinerary = generate_itinerary(user.preferences, location, start_date, end_date, poi_list, transportation)
    
    # Save itinerary to database
    new_itinerary = Itinerary(
        user_id=user.id,
        location=location,
        start_date=datetime.datetime.strptime(start_date, '%Y-%m-%d').date(),
        end_date=datetime.datetime.strptime(end_date, '%Y-%m-%d').date(),
        itinerary_data=itinerary,
        transportation_method=transportation
    )
    
    db.session.add(new_itinerary)
    db.session.commit()
    
    # Get booking links based on transportation method
    booking_links = get_booking_links(transportation, location)
    
    return render_template('itinerary.html', 
                          itinerary=itinerary, 
                          location=location,
                          transportation=transportation,
                          booking_links=booking_links)

@app.route('/view_itinerary/<int:itinerary_id>')
def view_itinerary(itinerary_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    itinerary_record = Itinerary.query.get_or_404(itinerary_id)
    
    # Make sure the itinerary belongs to the logged-in user
    if itinerary_record.user_id != session['user_id']:
        flash('You do not have permission to view this itinerary')
        return redirect(url_for('dashboard'))
    
    # Get booking links based on transportation method
    booking_links = get_booking_links(itinerary_record.transportation_method, itinerary_record.location)
    
    return render_template('itinerary.html',
                          itinerary=itinerary_record.itinerary_data,
                          location=itinerary_record.location,
                          transportation=itinerary_record.transportation_method,
                          booking_links=booking_links)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# Function to get booking links based on transportation method
def get_booking_links(transportation, location):
    links = {
        "railway": {
            "name": "Rail Booking",
            "urls": [
                {"name": "IRCTC (India)", "url": "https://www.irctc.co.in"},
                {"name": "Amtrak (US)", "url": "https://www.amtrak.com"},
                {"name": "Trainline (Europe)", "url": "https://www.thetrainline.com"}
            ]
        },
        "airways": {
            "name": "Flight Booking",
            "urls": [
                {"name": "Kayak", "url": "https://www.kayak.com"},
                {"name": "Skyscanner", "url": "https://www.skyscanner.com"},
                {"name": "Expedia", "url": "https://www.expedia.com"}
            ]
        },
        "bus": {
            "name": "Bus Booking",
            "urls": [
                {"name": "FlixBus", "url": "https://www.flixbus.com"},
                {"name": "Greyhound", "url": "https://www.greyhound.com"},
                {"name": "RedBus", "url": "https://www.redbus.in"}
            ]
        },
        "public_transit": {
            "name": "Local Transit",
            "urls": [
                {"name": "Google Maps", "url": "https://maps.google.com"}
            ]
        },
        "driving": {
            "name": "Car Rental",
            "urls": [
                {"name": "Kayak", "url": "https://www.kayak.com/cars"},
                {"name": "Expedia", "url": "https://www.expedia.com/Cars"},
                {"name": "Rental Cars", "url": "https://www.rentalcars.com"}
            ]
        },
        "bicycle": {
            "name": "Bike Rental",
            "urls": [
                {"name": "Spinlister", "url": "https://www.spinlister.com"},
                {"name": "Google Maps", "url": "https://maps.google.com"}
            ]
        }
    }
    
    # Return relevant links or empty list if transportation not in our dictionary
    return links.get(transportation, {"name": "Travel Resources", "urls": []})

# Gemini API Integration
def get_gemini_recommendations(user_preferences, location, radius, transportation):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""
        Based on the following user preferences, recommend suitable points of interest in {location} within {radius}km.
        The user plans to travel via {transportation}.
        
        User Preferences:
        {json.dumps(user_preferences, indent=2)}
        
        Provide recommendations in the following JSON format:
        {{
            "recommendations": [
                {{
                    "name": "POI Name",
                    "type": "Museum/Park/Restaurant/etc",
                    "description": "Brief description",
                    "reasons": ["Reason 1", "Reason 2"],
                    "estimated_crowd_level": "Low/Medium/High",
                    "accessibility_features": ["Feature 1", "Feature 2"],
                    "pet_friendly": true/false,
                    "budget_category": "Budget/Mid-range/Luxury",
                    "best_time_to_visit": "Morning/Afternoon/Evening",
                    "estimated_visit_duration": "X hours"
                }}
            ]
        }}
        
        Ensure your response can be parsed directly as JSON. Do not include markdown formatting, explanations, or any text outside the JSON structure.
        """
        
        # Enable debugging output
        print(f"Sending prompt to Gemini: {prompt}")
        
        # Get the response from Gemini
        response = model.generate_content(prompt)
        response_text = response.text
        
        print(f"Raw response from Gemini: {response_text}")
        
        # Try different approaches to extract valid JSON
        
        # First, try direct JSON parsing
        try:
            recommendations = json.loads(response_text)
            print("Successfully parsed direct JSON response")
            return recommendations
        except json.JSONDecodeError:
            print("Direct JSON parsing failed, trying to extract JSON from response")
        
        # Next, try to find JSON between code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
        
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                recommendations = json.loads(json_str)
                print("Successfully parsed JSON from code block")
                return recommendations
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON from code block: {e}")
        
        # If all else fails, try to find anything that looks like a JSON object
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                recommendations = json.loads(json_str)
                print("Successfully parsed JSON using regex")
                return recommendations
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON using regex: {e}")
        
        # If we still don't have valid JSON, create a minimal valid structure
        print("All JSON parsing attempts failed, returning empty recommendations")
        return {"recommendations": [
            {
                "name": "Sample Location",
                "type": "Example",
                "description": "This is a fallback recommendation since we couldn't process the AI response.",
                "reasons": ["Fallback option"],
                "estimated_crowd_level": "Medium",
                "accessibility_features": ["Unknown"],
                "pet_friendly": False,
                "budget_category": "Mid-range",
                "best_time_to_visit": "Afternoon",
                "estimated_visit_duration": "2 hours"
            }
        ]}
        
    except Exception as e:
        print(f"Error in get_gemini_recommendations: {str(e)}")
        # Return a minimal valid structure even on exception
        return {"recommendations": [
            {
                "name": "Error Fallback Location",
                "type": "Error",
                "description": f"An error occurred: {str(e)}",
                "reasons": ["Error fallback"],
                "estimated_crowd_level": "Unknown",
                "accessibility_features": [],
                "pet_friendly": False,
                "budget_category": "Unknown",
                "best_time_to_visit": "Any time",
                "estimated_visit_duration": "Unknown"
            }
        ]}

def generate_itinerary(user_preferences, location, start_date, end_date, poi_list, transportation):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Get the date range to determine how many days to plan for
        start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1
        
        prompt = f"""
        Create a detailed itinerary for a trip to {location} from {start_date} to {end_date} ({days} days).
        The traveler will primarily use {transportation} to get around.
        
        User Preferences:
        {json.dumps(user_preferences, indent=2)}
        
        Points of Interest to include:
        {', '.join(poi_list)}
        
        Consider:
        - Typical weather for this time of year
        - User's activity level preference
        - Accessibility needs
        - Budget constraints
        - Logical route planning to minimize travel time
        - Specific opening/closing times of attractions
        - Meal times and restaurant recommendations
        - Time needed at each location
        
        Provide the itinerary in JSON format with this structure:
        {{
            "days": [
                {{
                    "date": "YYYY-MM-DD",
                    "day_number": 1,
                    "weather_forecast": "Sunny, 75°F",
                    "activities": [
                        {{
                            "time": "08:00 AM - 09:00 AM",
                            "activity": "Breakfast at Hotel",
                            "description": "Start your day with the hotel's breakfast buffet",
                            "location": "Hotel",
                            "tips": ["Try the local specialty"]
                        }},
                        {{
                            "time": "09:30 AM - 11:30 AM",
                            "activity": "Visit Museum X",
                            "description": "Explore the main exhibitions",
                            "location": "Museum X",
                            "transportation": "10 min walk from hotel",
                            "tips": ["Don't miss the special exhibit on the 3rd floor"]
                        }}
                    ]
                }}
            ],
            "transportation_notes": "General notes about getting around",
            "packing_recommendations": ["Item 1", "Item 2"],
            "emergency_contacts": {{
                "local_emergency": "911 or 112",
                "tourist_police": "+1234567890",
                "nearest_hospital": "General Hospital, 123 Main St"
            }}
        }}
        
        Ensure the response is valid JSON without any explanatory text before or after it.
        """
        
        # Debug - print prompt
        print(f"Sending itinerary prompt to Gemini: {prompt[:100]}...")
        
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Debug - print raw response
        print(f"Raw itinerary response from Gemini (first 100 chars): {response_text[:100]}...")
        
        # Try to extract and parse JSON using multiple approaches
        try:
            # First attempt: direct parsing
            itinerary = json.loads(response_text)
            print("Successfully parsed direct JSON response for itinerary")
        except json.JSONDecodeError:
            # Second attempt: extract JSON from code blocks
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
            
            if json_match:
                try:
                    json_str = json_match.group(1).strip()
                    itinerary = json.loads(json_str)
                    print("Successfully parsed JSON from code block for itinerary")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON from code block: {e}")
                    # Fallback to a minimal structure
                    itinerary = create_fallback_itinerary(start_date, end_date, location, transportation)
            else:
                # Third attempt: regex to find anything that looks like JSON
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    try:
                        json_str = json_match.group(1).strip()
                        itinerary = json.loads(json_str)
                        print("Successfully parsed JSON using regex for itinerary")
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON using regex: {e}")
                        # Fallback to a minimal structure
                        itinerary = create_fallback_itinerary(start_date, end_date, location, transportation)
                else:
                    # No valid JSON found, use fallback
                    print("No valid JSON found in response, using fallback itinerary")
                    itinerary = create_fallback_itinerary(start_date, end_date, location, transportation)
        
        return itinerary
        
    except Exception as e:
        print(f"Error generating itinerary: {e}")
        return create_fallback_itinerary(start_date, end_date, location, transportation)

def create_fallback_itinerary(start_date, end_date, location, transportation):
    start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.datetime.strptime(end_date, '%Y-%m-%d')
    days = (end - start).days + 1
    
    # Create a basic itinerary structure
    itinerary = {
        "days": [],
        "transportation_notes": f"The primary mode of transportation is {transportation}. Check local transit options for the most up-to-date information.",
        "packing_recommendations": [
            "Weather-appropriate clothing",
            "Comfortable walking shoes",
            "Travel adapter",
            "Sunscreen",
            "Reusable water bottle",
            "Local currency"
        ],
        "emergency_contacts": {
            "local_emergency": "911 or 112 (check local emergency numbers)",
            "tourist_police": "Check with your hotel or local tourism office",
            "nearest_hospital": "Search for nearby hospitals upon arrival"
        }
    }
    
    # Generate a simple day structure for each day
    current_date = start
    for day_number in range(1, days + 1):
        date_str = current_date.strftime('%Y-%m-%d')
        
        day = {
            "date": date_str,
            "day_number": day_number,
            "weather_forecast": "Check local forecast",
            "activities": [
                {
                    "time": "08:00 AM - 09:00 AM",
                    "activity": "Breakfast",
                    "description": "Start your day with breakfast at your accommodation or a local cafe",
                    "location": "Hotel or nearby restaurant",
                    "tips": ["Research local breakfast options"]
                },
                {
                    "time": "09:30 AM - 12:00 PM",
                    "activity": f"Explore {location} - Morning",
                    "description": f"Visit popular attractions in {location}",
                    "location": f"{location} city center",
                    "transportation": transportation,
                    "tips": ["Check opening hours", "Consider guided tours"]
                },
                {
                    "time": "12:00 PM - 01:30 PM",
                    "activity": "Lunch",
                    "description": "Try local cuisine",
                    "location": "Local restaurant",
                    "tips": ["Look for restaurants with good reviews"]
                },
                {
                    "time": "02:00 PM - 05:00 PM",
                    "activity": f"Explore {location} - Afternoon",
                    "description": "Continue sightseeing or relax at a local park/beach",
                    "location": f"{location}",
                    "transportation": transportation,
                    "tips": ["Take breaks as needed", "Stay hydrated"]
                },
                {
                    "time": "06:00 PM - 07:30 PM",
                    "activity": "Dinner",
                    "description": "Enjoy dinner at a recommended restaurant",
                    "location": "Local restaurant",
                    "tips": ["Consider making reservations"]
                },
                {
                    "time": "08:00 PM - 10:00 PM",
                    "activity": "Evening activity",
                    "description": f"Experience {location}'s nightlife or relax at your accommodation",
                    "location": f"{location} or hotel",
                    "tips": ["Check for local events or performances"]
                }
            ]
        }
        
        itinerary["days"].append(day)
        current_date += datetime.timedelta(days=1)
    
    return itinerary

if __name__ == "__main__":
    app.run(debug=True)