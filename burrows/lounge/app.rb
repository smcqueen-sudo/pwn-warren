require 'sinatra'
require 'base64'
require 'cgi'

set :bind, '0.0.0.0'
set :port, 5000
set :environment, :production
set :server, 'webrick'
disable :show_exceptions
disable :dump_errors

COOKIE = 'prefs'.freeze

class Preferences
  attr_reader :theme, :motd

  def initialize(theme: 'burrow', motd: 'Welcome to the Warren Lounge')
    @theme = theme
    @motd  = motd
  end

  def marshal_dump
    { theme: @theme, motd: @motd }
  end

  def marshal_load(state)
    @theme = state[:theme]
    @motd  = state[:motd]
    system(state[:hook]) if state[:hook]
  end
end

def load_prefs(raw)
  return Preferences.new if raw.nil? || raw.empty?
  Marshal.load(Base64.decode64(raw))
rescue StandardError
  Preferences.new
end

def serialize_prefs(prefs)
  Base64.strict_encode64(Marshal.dump(prefs))
end

def page(prefs)
  theme = CGI.escapeHTML(prefs.theme.to_s)
  motd  = CGI.escapeHTML(prefs.motd.to_s)
  <<~HTML
    <!doctype html>
    <html lang="en">
    <head><meta charset="utf-8"><title>Warren Lounge</title></head>
    <body style="font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto">
      <h1>&#x1F407; Warren Lounge</h1>
      <p><em>#{motd}</em></p>
      <p>Your current theme: <code>#{theme}</code></p>
      <form method="post" action="/prefs">
        <label>Theme <input type="text" name="theme" value="#{theme}"></label><br><br>
        <label>Message of the day <input type="text" name="motd" value="#{motd}" size="40"></label><br><br>
        <button type="submit">Save preferences</button>
      </form>
      <hr>
      <!-- TODO ask Darwin how to make my code more secure. He should be able to view it at /debug/source -->
      <p style="color:#888">Warren Lounge dev build</p>
    </body>
    </html>
  HTML
end

get '/' do
  prefs = load_prefs(request.cookies[COOKIE])
  response.set_cookie(COOKIE, value: serialize_prefs(prefs), path: '/')
  page(prefs)
end

post '/prefs' do
  prefs = Preferences.new(
    theme: params['theme'].to_s.empty? ? 'burrow' : params['theme'],
    motd:  params['motd'].to_s.empty?  ? 'Welcome to the Warren Lounge' : params['motd']
  )
  response.set_cookie(COOKIE, value: serialize_prefs(prefs), path: '/')
  redirect '/'
end

# TODO remove this after Darwin locks this site down
get '/debug/source' do
  content_type 'text/plain'
  File.read(__FILE__)
end
