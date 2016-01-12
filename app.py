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
day_residuals = pd.read_csv('datafiles/Day_Residuals.csv', index_col = 0)
day_residuals.index = pd.to_datetime(day_residuals.index)

with open('datafiles/DoW_Factors.json') as json_data:
	DoW_Factors = json.load(json_data)
	json_data.close()

with open('datafiles/Month_Factors.json') as json_data:
	Month_Factors = json.load(json_data)
	json_data.close()

with open('datafiles/Hour_Factors.json') as json_data:
	Hour_Factors = json.load(json_data)
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
	
def Make_Zones_Plot(predicted_zone_starts, observed_zone_starts):
	rides = predicted_zone_starts+observed_zone_starts
	df = pd.DataFrame(rides)
	df['Group'] = ['Predicted']*5 + ['Observed']*5
	df['Zone'] = Zone_Names.tolist() * 2
	df.columns = ['Rides', 'Group', 'Zone']
	p = Bar(df, label='Zone', values='Rides', agg='median', group='Group',
        title="Predicted and Observed Rides by Zone", legend='top_right')
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
		predicted_hour_factors = pd.DataFrame(pd.DataFrame(Hour_Factors)*DoW_Factors[test_day.weekday()]*Month_Factors[test_day.month-1])
		predicted_starts = predicted_hour_factors*(DailyAvgStarts/24)
		actual_starts = pd.DataFrame([sum(test_day_starts.hour==hr) for hr in range(24)])
		hour_plot = Make_Hour_Plot(predicted_starts, actual_starts)
		day_total_prediction = predicted_starts.sum().tolist()
		zone_predictions = [Zone_Factors[zone]*(day_total_prediction[0]/5) for zone in range(5)]
		test_day_zones = Trip_Data.loc[selector, 'Zone']
		zone_observations = [np.NaN]*5
		for z_index, zone in enumerate(Zone_Names):
			zone_observations[z_index] = sum((test_day_zones==zone).tolist())
		zone_plot = Make_Zones_Plot(zone_predictions, zone_observations)
		
		script, div = components(hour_plot)
		script2, div2 = components(zone_plot)
		script = script+script2
		
		day = form.data['test_date']
		form = DateForm()
		tdr = day_residuals[day_residuals.index.date==test_day.date()].values[0]
		return render_template('results.html', form=form, date=day, plotscript=script, plotdiv=div, zonediv=div2, tdr=tdr)
		
def show_data():
	test_day='4/28/2014'
	test_day = pd.to_datetime(test_day)
	Start_Days = Trip_Times.date	
	selector = (Start_Days==test_day.date()).tolist()
	test_day_starts = pd.to_datetime(Trip_Times[selector])	
	predicted_hour_factors = pd.DataFrame(Hour_Factors*DoW_Factors[test_day.weekday()]*Month_Factors[test_day.month])
	predicted_starts = predicted_hour_factors*(DailyAvgStarts/24)
	actual_starts = pd.DataFrame([sum(test_day_starts.hour==hr) for hr in range(24)])
	hourly_changes = (actual_starts-predicted_starts)
		
if __name__ == '__main__':
  #port = int(os.environ.get("PORT", 5000))
  #app.run(host='0.0.0.0', port=port, debug=False)
  app.run(port=33507)