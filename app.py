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
import math
import holidays
from sklearn.externals import joblib
import sys
import logging

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

with open('datafiles/stn_monthly_data.json') as json_data:
    stn_monthly_data = json.load(json_data)

class DateForm(Form):
    test_date = fields.TextField('Test Date',  [
        validators.InputRequired(message='Test Date is Required')])
        
class HoursForm(Form):
    hours = fields.IntegerField('Hours from current time to predict', [
        validators.InputRequired(message='Integer number of hours required'),
        validators.NumberRange(min=0, max=1000, message='0-1000 hours only please')])

class PredictionForm(Form):
    time = fields.SelectField('Time to predict ', choices=[
      ('6h', '6 hours'),
      ('24h', '24 hours'),   
      ('1w', '1 week')])


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


def update_cartodb(mapdata, tablename):
    rows = []
    for station in station_ids:
        try:
            if mapdata.loc[int(station), 'total_docks']:
                rows.append(
            '(' +
            'CDB_LatLng(' + str(stations_df.loc[int(station), 'latitude']) + ', ' +
            str(stations_df.loc[int(station), 'longitude']) + '), ' +
            "'" + str(mapdata.loc[int(station), 'availableBikes']) + ' / ' + str(mapdata.loc[int(station), 'total_docks']) + "', " +
            "'" + str(stations_df.loc[int(station), 'stationName']) + "', " +
            "'" + str(int(mapdata.loc[int(station), 'pred_bikes'])) + ' / ' + str(mapdata.loc[int(station), 'total_docks']) + "', " +
            "'" + str(int(mapdata.loc[int(station), 'pred_change'])) + "', " +
            str(mapdata.loc[int(station), 'pred_bikes'] / float(mapdata.loc[int(station), 'total_docks']))
            + ')'
                )
        except:
            pass    
    delete = "TRUNCATE TABLE " + tablename
    insert = "INSERT INTO " + tablename + " (the_geom, current_bikes, name, predicted_bikes, predicted_change, status) (VALUES %s)" % ','.join(rows)
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


def update_cartodb_dist(mapdata, tablename):
    rows = []
    for station in station_ids:
        try:
            if mapdata.loc[int(station), 'total_docks']:
                rows.append(
            '(' +
            'CDB_LatLng(' + str(stations_df.loc[int(station), 'latitude']) + ', ' +
            str(stations_df.loc[int(station), 'longitude']) + '), ' +
            "'" + str(mapdata.loc[int(station), 'availableBikes']) + ' / ' + str(mapdata.loc[int(station), 'total_docks']) + "', " +
            "'" + str(stations_df.loc[int(station), 'stationName']) + "', " +
            "'" + str(int(mapdata.loc[int(station), 'pred_bikes'])) + ' / ' + str(mapdata.loc[int(station), 'total_docks']) + "', " +
            str(mapdata.loc[int(station), 'redist'])
            + ')'
                )
        except:
            pass  
    delete = "TRUNCATE TABLE " + tablename
    insert = "INSERT INTO " + tablename + " (the_geom, current_bikes, name, predicted_bikes, status) (VALUES %s)" % ','.join(rows)
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


@app.route('/choose-predictions', methods=['GET', 'POST'])
def choose_predictions():
    form = PredictionForm()
    return render_template('choose-predictions.html', form=form)


@app.route('/redistribute-24h', methods=['GET', 'POST'])
def redistribute_24h():
    return render_template('redistribute-24h.html')


@app.route('/redistribute-6h', methods=['GET', 'POST'])
def redistribute_6h():
    return render_template('redistribute-6h.html')


@app.route('/redistribute-1w', methods=['GET', 'POST'])
def redistribute_1w():
    return render_template('redistribute-1w.html')


@app.route('/model-details', methods=['GET', 'POST'])
def model_details():
    return render_template('model-details.html')


@app.route('/analysis', methods=['GET', 'POST'])
def analysis():
    return render_template('analysis.html')


@app.route('/live-predictions', methods=['GET', 'POST'])
def live_predictions():
    if request.method == 'GET':
        form = HoursForm()
        return render_template('live-predictions.html', form=form)
    else:
        form = PredictionForm(request.form)
        if not form.validate():
            return render_template('choose-predictions.html', form=form)
        if form.data['time'] == '6h':
            tablename = 'nyc_prediction_6h'
            disttablename = 'nyc_redistribution_6h'
            prediction_length = 6
        elif form.data['time'] == '24h':
            tablename = 'nyc_prediction'
            disttablename = 'nyc_redistribution'
            prediction_length = 24
        else:
            tablename = 'nyc_prediction_1w'
            disttablename = 'nyc_redistribution_1w'
            prediction_length = 168 
        
        ## Get live data from NY Citibike API --
        live_req = requests.get('https://www.citibikenyc.com/stations/json')
        live_data = live_req.json()
        start_time = pd.to_datetime(live_data['executionTime'])
        stations_df = pd.DataFrame(live_data['stationBeanList'])
        stations_df.index = stations_df['id'].tolist()
        
        # Get model predictions and compare to available bikes --
        predictions = get_predictions(start_time, prediction_length)    
        
        # Get predicted surpluses
        mapdata = pd.DataFrame(stations_df['availableBikes'].tolist(), columns=['availableBikes'], index=stations_df['id'].tolist())
        mapdata['pred_change'] = np.nan
        mapdata['pred_bikes'] = np.nan
        mapdata['total_docks'] = np.nan
        for stn in mapdata.index:
            if str(stn) in predictions.index:
                mapdata.loc[stn, 'pred_change'] = predictions.loc[(str(stn))]
                mapdata.loc[stn, 'pred_bikes'] = mapdata.loc[stn, 'availableBikes'] + predictions.loc[(str(stn))]
                mapdata.loc[stn, 'total_docks'] = stations_df.loc[stn, 'availableBikes'] + stations_df.loc[stn, 'availableDocks']                
        update_cartodb(mapdata, tablename)

        # Now compute redistributions
        stations_to_receive = []
        stations_to_give = []
        
        # Loop through stations and determine if they have bikes to give, or need bikes
        for stn in mapdata.index:
            try:
                stn_m_net = int(stn_monthly_data[str(stn)]['monthly_net'])
                stn_bikes = mapdata.loc[stn, 'pred_bikes']
                stn_capacity = mapdata.loc[stn, 'total_docks']
                stn_current = mapdata.loc[stn, 'availableBikes']       
                if stn_m_net > 0:  # these stations are gaining bikes
                    if stn_bikes < 1:
                        stations_to_receive.append([stn, int(stn_capacity / float(10))])
                    elif stn_bikes > .8 * stn_capacity:
                        max_give = int(stn_current - 3)  # Keep three bikes
                        optimal_give = int(stn_bikes - (stn_capacity * .25))
                        stations_to_give.append([stn, min(max_give, optimal_give)])
                else:              # these stations are losing bikes
                    if stn_bikes < 1:
                        to_fill = stn_capacity - stn_current - 2 # leave a couple open slots
                        for_month = -stn_m_net
                        stations_to_receive.append([stn, int(min(to_fill, for_month))])
                    elif stn_bikes > stn_capacity:
                        stations_to_give.append([stn, int(stn_bikes - (stn_capacity * .9))])
            except:
                pass   # So new stations don't crash the app
        give_df = pd.DataFrame(stations_to_give).sort(columns=[1], ascending=False)
        receive_df = pd.DataFrame(stations_to_receive).sort(columns=[1], ascending=False)
        total_gives = give_df.loc[:, 1].sum()
        
        # Roughly balance the gives and receives
        total_receives = receive_df.loc[:, 1].sum()
        if total_gives > total_receives:
            cumsum = give_df.loc[:, 1].cumsum()
            cumsum = cumsum < total_receives
            cumsum = cumsum.tolist()
            give_df = give_df[cumsum]
        else:
            cumsum = receive_df.loc[:, 1].cumsum()
            cumsum = cumsum < total_gives
            cumsum = cumsum.tolist()
            receive_df = receive_df[cumsum]
        mapdata['redist'] = np.nan
        for stn_index in receive_df.index:
            mapdata.loc[receive_df.loc[stn_index, 0], 'redist'] = receive_df.loc[stn_index, 1]
        for stn_index in give_df.index:
            mapdata.loc[give_df.loc[stn_index, 0], 'redist'] = -(give_df.loc[stn_index, 1])
        selector = np.isnan(mapdata['redist'])
        selector = [not x for x in selector]
        distdata = mapdata[selector]
        
        # Push the recommended distributions to cartodb for mapping
        update_cartodb_dist(distdata, disttablename)
        
        # Finally render first template with map of expected changes;
        # this map then links to the next map, of suggested redistributions
        if form.data['time'] == '6h':
            return render_template('live-results_6h.html', date=start_time, hours=prediction_length)
        elif form.data['time'] == '24h':
            return render_template('live-results_24h.html', date=start_time, hours=prediction_length)
        else:
            return render_template('live-results_1w.html', date=start_time, hours=prediction_length)        


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