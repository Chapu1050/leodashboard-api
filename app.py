from flask import Flask, render_template, request, jsonify
import requests
import datetime
from skyfield.api import EarthSatellite, load
import numpy as np
import pandas as pd
from plotly.subplots import make_subplots
import plotly.express as px
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

app = Flask(__name__)


@app.route('/', methods=['GET'])
def index():
    # Get the date inputs (allow multiple)
    date_strs = request.args.getlist('date_input')

    # Initialize a list to store plot divs
    plot_divs = []

    for date_str in date_strs:
        if not date_str:
            continue  # Skip if no date provided

        try:
            target_time = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return jsonify({"error": "Invalid date format. Please use 'YYYY-MM-DD HH:MM:SS'."})

        # Generate plots for the given date and append to the list
        plot_divs.append(generate_plots(target_time))

    return render_template('index.html', plot_divs=plot_divs)

def generate_plots(target_time):
    target_time_str = target_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://www.space-track.org/basicspacedata/query/class/gp/EPOCH/%3E{target_time_str}/MEAN_MOTION/%3E11.25/ECCENTRICITY/%3C0.25/OBJECT_TYPE/payload/orderby/NORAD_CAT_ID,EPOCH/format/3le"
    
    data = get_space_track_data(url, USERNAME, PASSWORD)
    if data is None:
        return "<p>No data available for the selected date.</p>"

    # Extract data and create DataFrame directly
    obj_names = []
    tle_line1 = []
    tle_line2 = []

    for i in range(0, len(data), 3):
        obj_names.append(data[i][2:])  # Remove leading characters
        tle_line1.append(data[i + 1])
        tle_line2.append(data[i + 2])
    
    # Create a DataFrame directly from lists
    satellites = [get_satellite(tle_line1[i], tle_line2[i]) for i in range(len(obj_names))]
    
    # Vectorized computation of altitudes and inclinations
    altitudes = np.array([sat.model.a * 6378.15 - 6378.15 for sat in satellites])
    inclinations = np.array([np.rad2deg(sat.model.inclo) for sat in satellites])

    # Create DataFrame from the altitudes and inclinations
    df = pd.DataFrame({'Altitude': altitudes, 'Inclination': inclinations})

    # Use groupby for aggregating data if needed or just create plots directly
    fig1 = px.density_heatmap(df, x='Altitude', y='Inclination', title=target_time.strftime("%Y-%m-%d %H:%M:%S"))
    fig2 = px.histogram(df, x='Altitude', title=target_time.strftime("%Y-%m-%d %H:%M:%S"))

    # Create a subplot and add traces
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Altitude Histogram", "Density Heatmap"))
    for trace in fig2.data:
        fig.add_trace(trace, row=1, col=1)
    for trace in fig1.data:
        fig.add_trace(trace, row=1, col=2)

    fig.update_layout(title_text="Plots as of " + target_time.strftime('%d/%m/%Y, %H:%M:%S'), width=1200, height=600)
    return fig.to_html(full_html=False)


def get_space_track_data(url, USERNAME, PASSWORD):
    with requests.Session() as session:
        login_url = 'https://www.space-track.org/ajaxauth/login'
        payload = {'identity': USERNAME, 'password': PASSWORD}
        login_response = session.post(login_url, data=payload)
        
        if login_response.status_code == 200:
            data_response = session.get(url)
            if data_response.status_code == 200:
                data_lines = data_response.text.splitlines()
                return data_lines
        return None

def get_satellite(tle_line1, tle_line2):
    satellite = EarthSatellite(tle_line1, tle_line2, 'Satellite', load.timescale())
    return satellite

if __name__ == "__main__":
    app.run(debug=True)
