# -*- coding: utf-8 -*-
"""
Created on Tue Jan 26 14:17:46 2016

@author: alhamood
"""

from flask import Flask, render_template, request, redirect, url_for
from wtforms import Form, validators, fields
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
import pandas as pd
import numpy as np
import math
import holidays
from sklearn.externals import joblib
import os
import sys
import logging
import time
import datetime

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
hourly_data_features = pd.read_csv('datafiles/hourly_data_features.csv', index_col=0)
hourly_data_features.index = pd.to_datetime(hourly_data_features.index)
us_holidays = holidays.UnitedStates()
weather_df = pd.read_csv('datafiles/weather_df.csv', index_col=0)
 
live_req = requests.get('https://www.citibikenyc.com/stations/json')
live_data = live_req.json()
start_time = pd.to_datetime(live_data['executionTime'])
stations_df = pd.DataFrame(live_data['stationBeanList'])
stations_df.index = stations_df['id'].tolist()
station_ids = weekday_start_factors.keys()
first_date = pd.to_datetime('2013-07-01')
last_date = pd.to_datetime('2015-11-30')

full_model = joblib.load('model/extra_trees.pkl')
trees_model = joblib.load('model/extra_trees_nw.pkl')
reg_tree = joblib.load('model/reg_tree.pkl')
feature_columns_noweath = ['System Day', 'DoYsin',
                   'DoYcos', 'HoDsin', 'HoDcos',
                    'DoWsin', 'DoWcos', 'Holiday']

class DateForm(Form):
    test_date = fields.TextField('Test Date',  [
        validators.InputRequired(message='Test Date is Required')])
        
class HoursForm(Form):
    hours = fields.IntegerField('Hours from current time to predict', [
        validators.InputRequired(message='Integer number of hours required'),
        validators.NumberRange(min=0, max=1000, message='0-1000 hours only please')])
        
def get_predictions(start_time, hours):
    if hours > 24:
        model = reg_tree
    else:
        model = trees_model
    net_ride_counter = (weekday_start_factors.loc[0] -
                        weekday_start_factors.loc[0]
                        )
    for predicted_hour in range(hours):
        hour_time = start_time + timedelta(hours=predicted_hour)
        tt = hour_time.timetuple()
        DoYsin = (math.sin(2 * math.pi * tt.tm_yday / 365))
        DoYcos = (math.cos(2 * math.pi * tt.tm_yday / 365))
        HoDsin = (math.sin(2 * math.pi * tt.tm_hour / 24))
        HoDcos = (math.cos(2 * math.pi * tt.tm_hour / 24))
        DoWsin = (math.sin(2 * math.pi * tt.tm_wday / 7))
        DoWcos = (math.cos(2 * math.pi * tt.tm_wday / 7))
        if hour_time in us_holidays:
            Holiday = (int(1))
        else:
            Holiday = (int(0))
        pred_hour_rides = model.predict((700, DoYsin, DoYcos, HoDsin, HoDcos, DoWsin, DoWcos, Holiday))[0]
        if hour_time.weekday() < 5:
            Station_Hour_Start_Factors = weekday_start_factors
            Station_Hour_End_Factors = weekday_end_factors
        else:
            Station_Hour_Start_Factors = weekend_start_factors
            Station_Hour_End_Factors = weekend_end_factors
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
    return render_template('index_new.html')
 

def Make_Hour_Plot(predicted_starts, observed_starts):
    p = figure(plot_width=500, plot_height=300, title='Hourly Ride Starts')
    p.line(range(24), observed_starts, color='firebrick', alpha = .8, legend='Observed', line_width=4)
    p.line(range(24), predicted_starts, color='navy', alpha = .5, legend='Predicted', line_width=4)
    p.xaxis.axis_label = 'Hour of Day'
    p.yaxis.axis_label = 'Number of rides'
    p.legend.orientation = "top_left"
    return p


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


@app.route('/model-test', methods=['GET', 'POST'])
def model_test():
    if request.method=='GET':
        form = DateForm()
        return render_template('model-test.html', form=form)
    else:
        form = DateForm(request.form)    
        if not form.validate():
            return render_template('model-test.html', form=form)
        test_day = form.data['test_date']
        try:
            test_day = pd.to_datetime(test_day)
        except ValueError:
            return render_template('baddate.html', msg='Sorry, date not understood. ', form=DateForm())
        if test_day < first_date:
            msg = 'Date not in dataset. First date is '+str(first_date.date())
            return render_template('baddate.html', msg=msg, form=DateForm())
        if test_day > last_date:
            msg = 'Date not in dataset. Last date is '+str(last_date.date())
            return render_template('baddate.html', msg=msg, form=DateForm())

        start_time = test_day 
        predicted_starts = []
        observed_starts = []
        for predicted_hour in range(24):
            hour_time = start_time + timedelta(hours=predicted_hour)
            tt = hour_time.timetuple()
            DoYsin = (math.sin(2 * math.pi * tt.tm_yday / 365))
            DoYcos = (math.cos(2 * math.pi * tt.tm_yday / 365))
            HoDsin = (math.sin(2 * math.pi * tt.tm_hour / 24))
            HoDcos = (math.cos(2 * math.pi * tt.tm_hour / 24))
            DoWsin = (math.sin(2 * math.pi * tt.tm_wday / 7))
            DoWcos = (math.cos(2 * math.pi * tt.tm_wday / 7))
            if hour_time in us_holidays:
                Holiday = (int(1))
            else:
                Holiday = (int(0))
            Tmax = (weather_df.loc[hour_time.date().strftime('%Y-%m-%d'), 't_max'])
            Tmin = (weather_df.loc[hour_time.date().strftime('%Y-%m-%d'), 't_min'])
            Precip = (weather_df.loc[hour_time.date().strftime('%Y-%m-%d'), 'precip'])
            Snow = (weather_df.loc[hour_time.date().strftime('%Y-%m-%d'), 'snow_depth'])
            Snowfall = (weather_df.loc[hour_time.date().strftime('%Y-%m-%d'), 'snowfall'])
            Wind = (weather_df.loc[hour_time.date().strftime('%Y-%m-%d'), 'windspeed'])
            
            predicted_starts.append(full_model.predict((700, DoYsin, DoYcos, HoDsin, HoDcos, DoWsin, DoWcos, Holiday,
                                                     Tmax, Tmin, Precip, Snow, Snowfall, Wind))[0])
            observed_starts.append(hourly_data_features.loc[hour_time, 'Rides'])                      
        
        hour_plot = Make_Hour_Plot(predicted_starts, observed_starts)

        script, div = components(hour_plot)

        day = form.data['test_date']
        form = DateForm()
        return render_template('results.html', form=form, date=day, plotscript=script, plotdiv=div)

if __name__ == '__main__':
    #port = int(os.environ.get("PORT", 5000))
    #app.run(host='0.0.0.0', port=port, debug=False)
    app.run(port=33507, debug=True)