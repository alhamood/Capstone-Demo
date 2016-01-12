# -*- coding: utf-8 -*-
"""
Created on Tue Jan  5 16:28:50 2016

@author: alhamood
"""

from flask import Flask, render_template, request, redirect
from wtforms import Form, validators, fields, widgets
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.charts import Bar

import numpy as np
import pandas as pd
import seaborn as sbc
import simplejson as json
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

day_residuals = pd.read_csv('datafiles/Day_Residuals.csv', index_col = 0)
day_residuals.index = pd.to_datetime(day_residuals.index)

Station_Hour_Start_Factors = pd.read_csv('datafiles/Station_Hour_Start_Factors.csv', index_col=0)
Station_Hour_End_Factors = pd.read_csv('datafiles/Station_Hour_End_Factors.csv', index_col=0)

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
	
with open('datafiles/Zone_Factors.json') as json_data:
	Zone_Factors = json.load(json_data)
	json_data.close()
	
Trip_Data = pd.read_csv('datafiles/Trip_Data.csv', index_col = 0)	
Trip_Data.index = pd.to_datetime(Trip_Data.index)
Trip_Times = Trip_Data.index
first_date = min(Trip_Times)
last_date = max(Trip_Times)
Zone_Names = Trip_Data['Zone'].unique()
Station_Names = DailyStarts.keys()
Station_Names = Station_Names.tolist()

with open('datafiles/Daily_Avg_Starts.json') as json_data:
	DailyAvgStarts = json.load(json_data)
	json_data.close()

class DateForm(Form):
	test_date = fields.TextField('Experiment Date',  [
	    validators.InputRequired(message='Experiment Date is Required')])

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
	#df.columns = ['NetBikes', 'Group', 'Station']
	p = Bar(df, label='Station', values='NetBikes', agg='median', group='Group',
        title="Predicted and Observed NetBikes by Station", legend='top_right')
	p.plot_width = 1300
	p.plot_height = 500
	p.y_range.start = -20
	p.y_range.end = 20
	return p

@app.route('/')
def main():
  return redirect('/index')    

@app.route('/index', methods=['GET', 'POST'])
def index():
	if request.method=='GET':
		form = DateForm()
		return render_template('index.html', form=form)
	else:
		form = DateForm(request.form)	
		if not form.validate():
			return render_template('index.html', form=form)
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
		Start_Days = Trip_Times.date
		selector = (Start_Days==test_day.date()).tolist()
		test_day_starts = pd.to_datetime(Trip_Times[selector])	
		if test_day.weekday() < 5:
			Hour_Factors = Hour_Factors_Weekdays
		else:
			Hour_Factors = Hour_Factors_Weekends
			
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
		tdr = day_residuals[day_residuals.index.date==test_day.date()].values[0]
		return render_template('results.html', form=form, date=day, plotscript=script, plotdiv=div, zonediv=div2, tdr=tdr)

		
if __name__ == '__main__':
    #port = int(os.environ.get("PORT", 5000))
    #app.run(host='0.0.0.0', port=port, debug=False)
    app.run(port=33507, debug=True)