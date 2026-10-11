"""Withhold Chart.js to verify startup rendering is not blocked; isolated Firebase."""
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1];fixture=(root/'tests/firebase-fixture.js').read_text();chart=urllib.request.urlopen('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',timeout=30).read()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);c=b.new_context(viewport={'width':390,'height':844});pending=[]
 def route(r):
  if 'chart.js' in r.request.url:pending.append(r)
  elif '/firebase-app.js' in r.request.url:r.fulfill(body=fixture,content_type='application/javascript')
  elif 'firebasejs/' in r.request.url:r.fulfill(body='',content_type='application/javascript')
  else:r.abort()
 c.route('https://**/*',route);page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8000/',wait_until='commit');page.locator('#bootSplash').wait_for(state='visible');page.wait_for_timeout(300)
 assert pending and page.evaluate("typeof Chart==='undefined'")
 assert page.evaluate("document.getElementById('bootSplash').getBoundingClientRect().height>0")
 assert page.evaluate("typeof restStopwatch==='object'")
 pending[0].fulfill(body=chart,content_type='application/javascript');page.wait_for_load_state('domcontentloaded');page.wait_for_timeout(1200)
 page.evaluate("records.bench.push({weight:60,reps:5,date:'26.10.11'});renderGraphForLift('bench')")
 assert page.evaluate('chartInstance instanceof Chart')
 page.evaluate('renderDietStatsChart(100,200);renderDietTrendChart();renderWeightTrendChart()')
 assert page.evaluate('dietStatsChartInstance instanceof Chart')
 assert not errors,errors
 print('PASS: splash and app initialize while Chart download is withheld; lift and diet charts work after deferred load')
 b.close()
