from flask import Flask, render_template, request, redirect, url_for, session
import requests
import os
from dotenv import load_dotenv
import subprocess
import json

print("Starting application...")  # Debug line

# Try to kill any existing Flask processes
try:
    if os.name == 'posix':  # For Mac/Linux
        subprocess.run(['pkill', '-f', 'flask'])
    elif os.name == 'nt':   # For Windows
        subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
except Exception as e:
    print(f"Note: Could not kill existing processes: {e}")

load_dotenv()
print(f"Loaded environment variables: GIBSON_API_KEY exists: {bool(os.getenv('GIBSON_API_KEY'))}")  # Debug line

app = Flask(__name__)
print(f"Absolute template path: {os.path.abspath(app.template_folder)}")  # New debug line
print(f"Template exists: {os.path.exists(os.path.join(app.template_folder, 'survey.html'))}")  # Add this line
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key-please-change')  # Please set this in .env

# Gibson API configuration
GIBSON_API_URL = "https://api.gibsonai.com/v1/-"
GIBSON_API_KEY = os.getenv('GIBSON_API_KEY')

headers = {
    "X-Gibson-API-Key": GIBSON_API_KEY,
    "Content-Type": "application/json"
}

# Add this mapping at the top of the file with other configurations
INDUSTRY_MAPPING = {
    "event_production": 1,
    "construction": 2,
    "catering": 3,
    "rental": 4,
    "municipality": 5,
    "emergency": 6,
    "other": 7,
    "": 8  # default value
}

def safe_float(value, default=0):
    """Convert value to float safely, returning default if conversion fails"""
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

@app.route('/')
def index():
    try:
        template_path = os.path.join(app.template_folder, 'survey.html')
        print(f"Trying to render template at: {template_path}")
        return render_template('survey.html')
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error details: {str(e)}")
        return f"Error loading survey: {str(e)}"

@app.route('/submit_survey', methods=['POST'])
def submit_survey():
    try:
        # Submit basic customer info
        customer_data = {
            "name": request.form.get('name') or "Anonymous",
            "email": request.form.get('email') or "no-email@example.com",
            "phone": request.form.get('phone') or "",
            "business_name": request.form.get('business_name') or "Anonymous Business",
            "industry": INDUSTRY_MAPPING.get(request.form.get('industry'), 7),
            "address": request.form.get('address') or "No Address",
            "state": request.form.get('state') or "NA",
            "zip_code": request.form.get('zip') or "00000"
        }

        print("\n=== CUSTOMER REQUEST ===")
        print(json.dumps(customer_data, indent=2))

        # Submit to API
        response = requests.post(
            f"{GIBSON_API_URL}/customer-information",
            headers=headers,
            json=customer_data
        )
        response.raise_for_status()
        
        # Get and store the customer UUID
        customer_uuid = response.json()['id_']['uuid']
        session['customer_uuid'] = customer_uuid

        # Get form data for calculations
        # Calculate total cost per event
        rental_cost = safe_float(request.form.get('rental_cost', 0))
        fuel_cost = safe_float(request.form.get('fuel_cost', 0))
        grounding_cost = safe_float(request.form.get('grounding_cost', 0))
        permit_cost = safe_float(request.form.get('permit_cost', 0))
        other_annual_costs = safe_float(request.form.get('maintenance_cost', 0))
        events_per_year = safe_float(request.form.get('events_per_year', 0))

        # Calculate cost per event (including portion of annual costs)
        cost_per_event = (
            rental_cost +  # Rental cost per event
            fuel_cost +    # Fuel cost per event
            grounding_cost +  # Grounding cost per event
            permit_cost +     # Permit cost per event
            (other_annual_costs / events_per_year if events_per_year > 0 else 0)  # Annual costs divided by number of events
        )

        # Calculate annual spend
        annual_temp_spend = cost_per_event * events_per_year

        # Calculate battery system details
        if 5 <= cost_per_event <= 20:
            battery_cost = 10000
            battery_capacity = "20kWh"
        elif 20 < cost_per_event <= 100:
            battery_cost = 50000
            battery_capacity = "100kWh"
        elif 100 < cost_per_event <= 250:
            battery_cost = 200000
            battery_capacity = "250kWh"
        elif 250 < cost_per_event <= 500:
            battery_cost = 400000
            battery_capacity = "500kWh"
        else:
            battery_cost = 50000  # Default
            battery_capacity = "100kWh"

        # Calculate hybrid system costs (battery + generator)
        hybrid_battery_cost = battery_cost / 2  # Half size battery
        annual_fuel_cost = fuel_cost * events_per_year
        hybrid_fuel_savings = annual_fuel_cost * 0.8  # 80% fuel savings
        
        # Calculate solar canopy addition
        industry = request.form.get('industry')
        
        # Determine if solar canopy is recommended
        solar_recommended = False
        if industry in ['event_production', 'rental'] and events_per_year > 20:
            solar_recommended = True
            solar_cost = battery_cost * 0.5  # Assume solar costs 50% of battery system
            solar_savings = annual_fuel_cost * 0.3  # Additional 30% savings
        else:
            solar_cost = 0
            solar_savings = 0

        # Calculate months to break even
        months_to_breakeven = (battery_cost / (annual_temp_spend / 12)) if annual_temp_spend > 0 else float('inf')

        # Calculate lifetime savings (7 years)
        lifetime_savings = (annual_temp_spend * 7) - battery_cost

        # Store all calculations in session
        session['calculations'] = {
            'annual_temp_spend': annual_temp_spend,
            'battery_cost': battery_cost,
            'battery_capacity': battery_capacity if 'battery_capacity' in locals() else "100kWh",
            'months_to_breakeven': months_to_breakeven,
            'lifetime_savings': lifetime_savings,
            'events_per_year': events_per_year,
            'cost_per_event': cost_per_event,
            'peak_power': cost_per_event,
            'hybrid_battery_cost': hybrid_battery_cost if 'hybrid_battery_cost' in locals() else battery_cost/2,
            'hybrid_fuel_savings': hybrid_fuel_savings if 'hybrid_fuel_savings' in locals() else 0,
            'solar_recommended': solar_recommended if 'solar_recommended' in locals() else False,
            'solar_cost': solar_cost if 'solar_cost' in locals() else 0,
            'solar_savings': solar_savings if 'solar_savings' in locals() else 0,
            'annual_fuel_cost': annual_fuel_cost if 'annual_fuel_cost' in locals() else 0,
            'state': customer_data['state'],
            'rental_cost': rental_cost,
            'fuel_cost': fuel_cost,
            'grounding_cost': grounding_cost,
            'permit_cost': permit_cost,
            'other_annual_costs': other_annual_costs
        }

        return redirect(url_for('results'))

    except Exception as e:
        print(f"\n=== ERROR ===\n{str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/results')
def results():
    calculations = session.get('calculations', {})
    customer_uuid = session.get('customer_uuid')
    
    if not customer_uuid:
        return redirect(url_for('index'))
    
    try:
        # Try to get API results, but don't fail if we can't
        api_results = {}
        try:
            results_response = requests.get(
                f"{GIBSON_API_URL}/customer-results/{customer_uuid}",
                headers=headers
            )
            results_response.raise_for_status()
            api_results = results_response.json()
        except:
            print("Could not fetch API results, showing calculations only")
        
        return render_template('results.html', 
                             results=api_results,
                             calculations=calculations)
        
    except Exception as e:
        print(f"Error rendering results: {str(e)}")
        return f"Error showing results: {str(e)}", 500

if __name__ == '__main__':
    ports_to_try = [5050, 5051, 5052, 5053]  # Using completely different ports
    
    for port in ports_to_try:
        try:
            print(f"Starting Flask server on port {port}...")
            app.run(debug=True, port=port, host='0.0.0.0')
            break  # If successful, exit the loop
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"Port {port} is in use, trying next port...")
                continue
            else:
                raise e
