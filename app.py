# -*- coding: utf-8 -*-
"""
Created on Tue Jan  5 16:28:50 2016

@author: alhamood
"""

from flask import Flask, render_template, request
from wtforms import Form, validators, fields, widgets

import numpy as np
import pandas as pd
import seaborn as sbc
import simplejson as json
import os

app = Flask(__name__)

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
	
with open('datafiles/TripTimes.json') as json_data:
	Trip_Times = json.load(json_data)
	json_data.close()
Trip_Times = pd.to_datetime(Trip_Times)
first_date = min(Trip_Times)
last_date = max(Trip_Times)

with open('datafiles/Daily_Avg_Starts.json') as json_data:
	DailyAvgStarts = json.load(json_data)
	json_data.close()

class DateForm(Form):
	test_date = fields.TextField('Experiment Date',  [
	    validators.InputRequired(message='Experiment Date is Required')])

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
		hourly_changes = (actual_starts-predicted_starts)
		hourly_changes.columns = ['Deviation from expected number of rides']		
		hours_html = hourly_changes.to_html()
		day = form.data['test_date']
		form = DateForm()
		tdr = day_residuals[day_residuals.index.date==test_day.date()].values[0]
		return render_template('results.html', form=form, date=day, table_html=hours_html, tdr=tdr)
		
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
  port = int(os.environ.get("PORT", 5000))
  app.run(host='0.0.0.0', port=port, debug=False)