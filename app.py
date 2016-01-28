# -*- coding: utf-8 -*-
"""
Created on Tue Jan 26 14:17:46 2016

@author: alhamood
"""

from flask import Flask, render_template, request, redirect, url_for
from wtforms import Form, validators, fields, widgets
import numpy as np
import pandas as pd
import simplejson as json
import requests
import urllib
import urllib2
from datetime import timedelta
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.charts import Bar, show, output_file
import os
import sys
import logging
import time

app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

API_KEY = '08c1d0b3694842112c27abb5ee901aca76955417'
username = 'alhamood'

# Load model components
weekday_start_factors = pd.read_csv('datafiles/weekday_start_factors_nov15.csv', index_col=0)
weekday_end_factors = pd.read_csv('datafiles/weekday_end_factors_nov15.csv', index_col=0)
weekend_start_factors = pd.read_csv('datafiles/weekend_start_factors_nov15.csv', index_col=0)
weekend_end_factors = pd.read_csv('datafiles/weekend_end_factors_nov15.csv', index_col=0)
live_req = requests.get('https://www.citibikenyc.com/stations/json')
live_data = live_req.json()
start_time = pd.to_datetime(live_data['executionTime'])
stations_df = pd.DataFrame(live_data['stationBeanList'])
stations_df.index = stations_df['id'].tolist()
station_ids = weekday_start_factors.keys()
weekday_avg_starts = 25782.42
weekday_avg_ends = 25775.65
weekend_avg_starts = 20221.94
weekend_avg_ends = 20237.42

weekday_month_factors = pd.read_csv('datafiles/weekday_month_factors.csv', index_col=0)
weekend_month_factors = pd.read_csv('datafiles/weekend_month_factors.csv', index_col=0)
weekday_hour_factors = pd.read_csv('datafiles/weekday_hour_factors.csv', index_col=0)
weekend_hour_factors = pd.read_csv('datafiles/weekend_hour_factors.csv', index_col=0)

class DateForm(Form):
    test_date = fields.TextField('Experiment Date',  [
        validators.InputRequired(message='Experiment Date is Required')])
        
class HoursForm(Form):
    hours = fields.IntegerField('Hours from current time to predict', [
        validators.InputRequired(message='Integer number of hours required'),
        validators.NumberRange(min=0, max=1000, message='0-1000 hours only please')])
        
def get_predictions(start_time, hours):
    net_ride_counter = (weekday_start_factors.loc[0] -
                        weekday_start_factors.loc[0]
                        )
    for predicted_hour in range(hours):
        hour_time = start_time + timedelta(hours=predicted_hour)
        if hour_time.weekday() < 5:
            Station_Hour_Start_Factors = weekday_start_factors
            Station_Hour_End_Factors = weekday_end_factors
            pred_hour_rides = weekday_avg_starts * weekday_month_factors.loc[hour_time.month-1, 'factors'] * weekday_hour_factors.loc[hour_time.hour, 'factors']
        else:
            Station_Hour_Start_Factors = weekend_start_factors
            Station_Hour_End_Factors = weekend_end_factors
            pred_hour_rides = weekend_avg_starts * weekend_month_factors.loc[hour_time.month-1, 'factors'] * weekend_hour_factors.loc[hour_time.hour, 'factors']
        pred_hour_starts = Station_Hour_Start_Factors.loc[hour_time.hour, :] * pred_hour_rides
        pred_hour_ends = Station_Hour_End_Factors.loc[hour_time.hour, :] * pred_hour_rides
        pred_hour_nets = (pred_hour_ends -
                          pred_hour_starts
                          )
        net_ride_counter = net_ride_counter + pred_hour_nets
    return net_ride_counter


def update_cartodb(values):
    rows = []
    for index, station in enumerate(station_ids):
        try:
            rows.append(
            '(' +
            'CDB_LatLng(' + str(stations_df.loc[int(station), 'latitude']) + ', ' +
            str(stations_df.loc[int(station), 'longitude']) + '), ' +
            str(values[index]) 
            + ')'
            )
        except:
            pass
    delete = "TRUNCATE TABLE nyc_netbikes"
    insert = "INSERT INTO nyc_netbikes (the_geom, predicted_net_bikes) (VALUES %s)" % ','.join(rows)
    url = "https://%s.cartodb.com/api/v1/sql" % username
    params = {
        'api_key' : API_KEY, # our account apikey, don't share!
        'q'       : delete  # our d statement above
    }
    req = urllib2.Request(url, urllib.urlencode(params))
    response = urllib2.urlopen(req)
    params = {
        'api_key' : API_KEY, # our account apikey, don't share!
        'q'       : insert  # our insert statement above
    }
    req = urllib2.Request(url, urllib.urlencode(params))
    response = urllib2.urlopen(req)
    response.close()


def update_cartodb2(values):
    rows = []
    for index, station in enumerate(station_ids):
        try:
            rows.append(
            '(' +
            'CDB_LatLng(' + str(stations_df.loc[int(station), 'latitude']) + ', ' +
            str(stations_df.loc[int(station), 'longitude']) + '), ' +
            str(values.loc[int(station), 0]) 
            + ')'
            )
        except:
            pass
    delete = "TRUNCATE TABLE nyc_surpluses"
    insert = "INSERT INTO nyc_surpluses (the_geom, predicted_surplus) (VALUES %s)" % ','.join(rows)
    url = "https://%s.cartodb.com/api/v1/sql" % username
    params = {
        'api_key' : API_KEY, # our account apikey, don't share!
        'q'       : delete  # our d statement above
    }
    req = urllib2.Request(url, urllib.urlencode(params))
    response = urllib2.urlopen(req)
    params = {
        'api_key' : API_KEY, # our account apikey, don't share!
        'q'       : insert  # our insert statement above
    }
    req = urllib2.Request(url, urllib.urlencode(params))
    response = urllib2.urlopen(req)
    response.close()


@app.route('/')
def main():
    return redirect('/index')
  

@app.route('/index')
def index():
    return redirect('/live-predictions')
 

@app.route('/live-predictions', methods=['GET', 'POST'])
def live_predictions():
    if request.method == 'GET':
        form = HoursForm()
        return render_template('live-predictions.html', form=form)
    else:
        form = HoursForm(request.form)
        if not form.validate():
            return render_template('live-predictions.html', form=form)
        prediction_length = form.data['hours']
        
        ## Get live data from NY Citibike API --
        live_req = requests.get('https://www.citibikenyc.com/stations/json')
        live_data = live_req.json()
        start_time = pd.to_datetime(live_data['executionTime'])
        stations_df = pd.DataFrame(live_data['stationBeanList'])
        stations_df.index = stations_df['id'].tolist()
        
        # Get model predictions and compare to available bikes --
        predictions = get_predictions(start_time, prediction_length)    
        update_cartodb(predictions.tolist())
        
        # Get predicted surpluses
        surpluses = pd.DataFrame(stations_df['availableBikes'].tolist(), index=stations_df['id'].tolist())
        for stn in surpluses.index:
            if str(stn) in predictions.index:
                surpluses.loc[stn] += predictions.loc[(str(stn))]
        update_cartodb2(surpluses)
        
        
        form = HoursForm()
        return render_template('live-results.html', form=form, date=start_time, hours=prediction_length)


if __name__ == '__main__':
    #port = int(os.environ.get("PORT", 5000))
    #app.run(host='0.0.0.0', port=port, debug=False)
    app.run(port=33507, debug=True)