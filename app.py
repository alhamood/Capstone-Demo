# -*- coding: utf-8 -*-
"""
Created on Mon Jan 18 12:32:20 2016

@author: alhamood
"""
from flask import Flask, render_template, request, redirect, url_for
from wtforms import Form, validators, fields, widgets
import numpy as np
import pandas as pd
import simplejson as json
import requests
from datetime import timedelta
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.charts import Bar, show, output_file
import os
import sys
import logging


app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

# Load model components
DailyStarts = pd.read_csv('datafiles/DailyStarts.csv', index_col = 0)
DailyStarts.index = pd.to_datetime(DailyStarts.index, infer_datetime_format=True)

DailyEnds = pd.read_csv('datafiles/DailyEnds.csv', index_col = 0)
DailyEnds.index = pd.to_datetime(DailyEnds.index, infer_datetime_format=True)

#day_residuals = pd.read_csv('datafiles/Day_Residuals.csv', index_col = 0)
#day_residuals.index = pd.to_datetime(day_residuals.index)

Station_Weekday_Hour_Start_Factors = pd.read_csv('datafiles/Station_Weekday_Hour_Start_Factors.csv', index_col=0)
Station_Weekday_Hour_End_Factors = pd.read_csv('datafiles/Station_Weekday_Hour_End_Factors.csv', index_col=0)

Station_Weekend_Hour_Start_Factors = pd.read_csv('datafiles/Station_Weekend_Hour_Start_Factors.csv', index_col=0)
Station_Weekend_Hour_End_Factors = pd.read_csv('datafiles/Station_Weekend_Hour_End_Factors.csv', index_col=0)

Trip_Data = pd.read_csv('datafiles/Trip_Data.csv', index_col=0)
Trip_Data.index = pd.to_datetime(Trip_Data.index, infer_datetime_format=True)


with open('datafiles/DoW_Factors.json') as json_data:
	DoW_Factors = json.load(json_data)
	json_data.close()

with open('datafiles/Month_Factors.json') as json_data:
	Month_Factors = json.load(json_data)
	json_data.close()

with open('datafiles/Hour_Factors_Weekdays.json') as json_data:
	Hour_Factors_Weekdays = json.load(json_data)
	json_data.close()

with open('datafiles/Hour_Factors_Weekends.json') as json_data:
	Hour_Factors_Weekends = json.load(json_data)
	json_data.close()

first_date = min(DailyStarts.index)
last_date = max(DailyStarts.index)
Station_Names = DailyStarts.keys()
Station_Names = Station_Names.tolist()

with open('datafiles/Daily_Avg_Starts.json') as json_data:
	DailyAvgStarts = json.load(json_data)
	json_data.close()


class DateForm(Form):
    test_date = fields.TextField('Experiment Date',  [
        validators.InputRequired(message='Experiment Date is Required')])


class HoursForm(Form):
    hours = fields.IntegerField('Hours from current time to predict', [
        validators.InputRequired(message='Integer number of hours required'),
        validators.NumberRange(min=0, max=1000, message='0-1000 hours only please')])


def Make_Hour_Plot(predicted_starts, observed_starts):
    p = figure(plot_width=500, plot_height=300, title='Hourly Ride Starts')
    p.line(range(24), observed_starts[0].tolist(), color='firebrick', alpha = .8, legend='Observed', line_width=4)
    p.line(range(24), predicted_starts[0].tolist(), color='navy', alpha = .5, legend='Predicted', line_width=4)
    p.xaxis.axis_label = 'Hour of Day'
    p.yaxis.axis_label = 'Number of rides'
    p.legend.orientation = "top_left"
    return p


def Make_Stations_Plot(predicted_nets, observed_nets):
    net_bikes = predicted_nets+observed_nets
    df = pd.DataFrame(columns=['NetBikes', 'Group', 'Station'])
    df['NetBikes'] = net_bikes
    df['Group'] = ['Predicted']*len(Station_Names) + ['Observed']*len(Station_Names)
    df['Station'] = Station_Names * 2
    p = Bar(df, label='Station', values='NetBikes', agg='median', group='Group',
        title="Predicted and Observed NetBikes by Station", legend='top_right', xgrid=True)
    p.plot_width = 1300
    p.plot_height = 500
    p.y_range.start = -20
    p.y_range.end = 20
    return p
     

def Make_Netbikes_Prediction_Plot(predicted_nets, current_bikes):
    net_bikes = predicted_nets + current_bikes
    pdf = pd.DataFrame(columns=['NetBikes', 'Group', 'Station'])
    pdf['NetBikes'] = net_bikes
    pdf['Group'] = ['Predicted Net Bikes'] * len(Station_Names) + ['Current Supply'] * len(Station_Names)
    pdf['Station'] = Station_Names * 2
    p = Bar(pdf, label='Station', values='NetBikes', agg='median', group='Group',
    title="Predicted Net Bikes and Current Bikes by Station", legend='top_right', xgrid=True)
    p.plot_width = 1300
    p.plot_height = 500
    p.y_range.start = -20
    p.y_range.end = 20
    return p
 

def get_predictions(start_time, hours):
    net_ride_counter = (Station_Weekday_Hour_Start_Factors.loc[0] -
                        Station_Weekday_Hour_Start_Factors.loc[0]
                        )
    for predicted_hour in range(hours):
        hour_time = start_time + timedelta(hours=predicted_hour)
        if hour_time.weekday() < 5:
            Station_Hour_Start_Factors = Station_Weekday_Hour_Start_Factors
            Station_Hour_End_Factors = Station_Weekday_Hour_End_Factors
        else:
            Station_Hour_Start_Factors = Station_Weekend_Hour_Start_Factors
            Station_Hour_End_Factors = Station_Weekend_Hour_End_Factors
        pred_day_rides = DailyAvgStarts  # banal!
        pred_hour_starts = Station_Hour_Start_Factors * pred_day_rides
        pred_hour_ends = Station_Hour_End_Factors * pred_day_rides
        pred_hour_nets = (pred_hour_ends.loc[hour_time.hour] -
                          pred_hour_starts.loc[hour_time.hour]
                          )
        net_ride_counter = net_ride_counter + pred_hour_nets
    return net_ride_counter


@app.route('/')
def main():
    return redirect('/index')


@app.route('/index')
def index():
    return render_template('index.html')


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
        Trip_Times = Trip_Data.index
        Start_Days = Trip_Times.date
        selector = (Start_Days==test_day.date()).tolist()
        test_day_starts = pd.to_datetime(Trip_Times[selector])

        if test_day.weekday() < 5:
            Hour_Factors = Hour_Factors_Weekdays
            Station_Hour_Start_Factors = Station_Weekday_Hour_Start_Factors
            Station_Hour_End_Factors = Station_Weekday_Hour_End_Factors
        else:
            Hour_Factors = Hour_Factors_Weekends
            Station_Hour_Start_Factors = Station_Weekend_Hour_Start_Factors
            Station_Hour_End_Factors = Station_Weekend_Hour_End_Factors
                        
        predicted_hour_factors = pd.DataFrame(pd.DataFrame(Hour_Factors)*DoW_Factors[test_day.weekday()]*Month_Factors[test_day.month-1])
        predicted_starts = predicted_hour_factors*(DailyAvgStarts/24)
        actual_starts = pd.DataFrame([sum(test_day_starts.hour==hr) for hr in range(24)])
        hour_plot = Make_Hour_Plot(predicted_starts, actual_starts)

        day_total_prediction = predicted_starts.sum().tolist()
        day_total_prediction = day_total_prediction[0]
        start_predictions = Station_Hour_Start_Factors.sum() * day_total_prediction
        end_predictions = Station_Hour_End_Factors.sum() * day_total_prediction
        net_predictions = (end_predictions-start_predictions).tolist()

        start_observations = DailyStarts[(DailyStarts.index.date==test_day.date())]
        end_observations = DailyEnds[(DailyEnds.index.date==test_day.date())]
        net_observations = np.array(end_observations-start_observations)
        net_observations = net_observations[0].tolist()

        zone_plot = Make_Stations_Plot(net_predictions, net_observations)

        script, div = components(hour_plot)
        script2, div2 = components(zone_plot)
        script = script+script2

        day = form.data['test_date']
        form = DateForm()
        return render_template('results.html', form=form, date=day, plotscript=script, plotdiv=div, zonediv=div2)


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
        url = 'http://www.bayareabikeshare.com/stations/json'
        live_req = requests.get('http://www.bayareabikeshare.com/stations/json')
        live_data = live_req.json()
        df = pd.DataFrame(live_data['stationBeanList'])
        df.index = df['id']
        start_time = pd.to_datetime(live_data['executionTime'])
        predictions = get_predictions(start_time, prediction_length)
        p = Make_Netbikes_Prediction_Plot(predictions.tolist(), df['availableBikes'].tolist())
        script, div = components(p)
        form = HoursForm()
        return render_template('live-results.html', form=form, date=start_time, plotscript=script, plotdiv=div, hours=prediction_length) 
        

        
if __name__ == '__main__':
    #port = int(os.environ.get("PORT", 5000))
    #app.run(host='0.0.0.0', port=port, debug=False)
    app.run(port=33507, debug=True)
