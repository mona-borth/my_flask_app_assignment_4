from flask import render_template, flash, redirect, url_for, request
from flaskapp import app, db
from flaskapp.models import BlogPost, IpView, Day, UkData
from flaskapp.forms import PostForm
import datetime

import pandas as pd
import json
import plotly
import plotly.express as px
import numpy as np


# Route for the home page, which is where the blog posts will be shown
@app.route("/")
@app.route("/home")
def home():
    # Querying all blog posts from the database
    posts = BlogPost.query.all()
    return render_template('home.html', posts=posts)


# Route for the about page
@app.route("/about")
def about():
    return render_template('about.html', title='About page')


# Route to where users add posts (needs to accept get and post requests)
@app.route("/post/new", methods=['GET', 'POST'])
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = BlogPost(title=form.title.data, content=form.content.data, user_id=1)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post', form=form)


# Route to the dashboard page
@app.route('/dashboard')
def dashboard():
    days = Day.query.all()
    df = pd.DataFrame([{'Date': day.id, 'Page views': day.views} for day in days])

    fig = px.bar(df, x='Date', y='Page views')

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template('dashboard.html', title='Page views per day', graphJSON=graphJSON)

# Route to the dashboard page
@app.route('/demography2')
def demography2():
    rows = (
    UkData.query
    .with_entities(
        UkData.country,
        UkData.region,
        UkData.Turnout19,
        UkData.c11Female
    )
    .all())

    df = (
        pd.DataFrame(rows, columns=['Country','Region','Turnout', 'Female'])
        .groupby(['Country','Region'], as_index=False)
        .mean()          # if you have multiple entries per region
        .sort_values('Turnout', ascending=False)
    )
 
    fig = px.bar(
        df,
        x='Region',
        y='Turnout',
        color='Female',
        labels={'Turnout':'Turnout (%)',
                'Female':  'Share of Women in the Population (%)'},
        text='Region',
        hover_data={
        'Region': True,
        'Turnout': ':.1f',   # one decimal place
        'Female': ':.1f'
        },
        color_continuous_scale=px.colors.sequential.Viridis,
        range_color=[50, 52]  # set the range of the color scale
    )

    fig_html = fig.to_html(full_html=False)
    return render_template('dashboard.html', title='2019 Turnout by Region, Coloured by Share of Women in the Population', fig_html=fig_html)

@app.route('/demography1')
def demography1():
    rows = (UkData.query
    .with_entities(
        UkData.c11Retired,
        UkData.Turnout19,
        UkData.BrexitVote19,
        UkData.TotalVote19,
        UkData.country,
        UkData.constituency_name
    )
    .filter(UkData.country == 'England')
    .all()
    )

    df = (pd.DataFrame(rows, columns=['Retiree', 'Turnout', 'BrexitVotes', 'TotalVotes', 'Country', 'Constituency']))

    df['Brexit'] = df['BrexitVotes'] / df['TotalVotes']*100 # get Brexit Party vote share in percent
    df = df.fillna({'Brexit': 0})

    # Split data for plotting
    df_nonzero = df[df['Brexit'] > 0]
    df_zero = df[df['Brexit'] == 0]

    # Plot with non-zero Brexit party votes
    fig = px.scatter(
        df_nonzero,
        x='Retiree',
        y='Turnout',
        size='Brexit',
        size_max=30,
        color='Brexit',
        hover_data={
            'Retiree': ':.1f',
            'Turnout': ':.1f',
            'BrexitVotes': False,
            'TotalVotes': False,
            'Brexit': ':.2f',
            'Constituency': True
        },
        labels={
            'Retiree': 'Retiree (pct of population retired)',
            'Turnout': 'Turnout (pct of electorate)',
            'Brexit': 'Brexit Party Vote (pct)'
        },
        range_color=[0, 35]
    )

    # Add zero points
    fig.add_scatter(
        x=df_zero['Retiree'],
        y=df_zero['Turnout'],
        mode='markers',
        marker=dict(size=4, symbol='circle', color='darkblue'),
        showlegend=False,
        customdata=np.stack([df_zero['Constituency'], df_zero['Brexit']], axis=1), # with help of ChatGPT for showing hover data correctly
        hovertemplate=(
            "Retiree (pct of population retired)=%{x:.1f}<br>"
            "Turnout (pct of electorate)=%{y:.1f}<br>"
            "Brexit Party Vote (pct)=0.0<br>"
            "Constituency=%{customdata[0]}<extra></extra>"
    )
    )
    
    fig_html = fig.to_html(full_html=False)

    return render_template('dashboard.html', title='Turnout, Retirees, and Brexit Party vote in Parliamentary Constituencies in England', fig_html=fig_html)

@app.before_request
def before_request_func():
    day_id = datetime.date.today()  # get our day_id
    client_ip = request.remote_addr  # get the ip address of where the client request came from

    query = Day.query.filter_by(id=day_id)  # try to get the row associated to the current day
    if query.count() > 0:
        # the current day is already in table, simply increment its views
        current_day = query.first()
        current_day.views += 1
    else:
        # the current day does not exist, it's the first view for the day.
        current_day = Day(id=day_id, views=1)
        db.session.add(current_day)  # insert a new day into the day table

    query = IpView.query.filter_by(ip=client_ip, date_id=day_id)
    if query.count() == 0:  # check if it's the first time a viewer from this ip address is viewing the website
        ip_view = IpView(ip=client_ip, date_id=day_id)
        db.session.add(ip_view)  # insert into the ip_view table

    db.session.commit()  # commit all the changes to the database
