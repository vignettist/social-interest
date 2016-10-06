from selenium import webdriver
import json
import time
import datetime
import sys
from wand.image import Image
import wand.exceptions
import requests
from StringIO import StringIO
from pymongo import MongoClient

basepath = '/Volumes/Manganese/facebook-images/'
username = 'williams.logan'

with open('cookies.json') as data_file:    
  cookies = json.load(data_file)

def scrollToBottom(driver):
    attempts = 0
    lastheight = 0

    while (attempts < 15):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sys.stdout.write('.')
        sleep(0.1)

        height = driver.execute_script("return(document.body.scrollHeight);")
        if (height == lastheight):
            attempts += 1
        else:
            attempts = 0
            lastheight = height
    
    print('o')

def getUserIds(driver):
    driver.get('https://m.facebook.com/' + username + '/friends/');
    
    scrollToBottom(driver)
    
    user_ids = set()
    
    user_elements = driver.find_elements_by_css_selector('._52jh a')
    
    for user_element in user_elements:
        user_link = user_element.get_attribute('href')
        if user_link is not None:
            user = user_link[23:].split('/')[0]
            if (user is not 'settings') and (user is not 'findfriends'):
                user_ids.add(user)
    
    return list(user_ids)

def getPhotoIds(driver):
    links = driver.find_elements_by_tag_name('a')
    photo_ids = set()

    for link in links:
        if link.get_attribute('href') is not None:
            if 'facebook.com/photo.php' in link.get_attribute('href'):
                photo_ids.add(link.get_attribute('href').split('fbid=')[1].split('&')[0])
    
    return photo_ids

def getPhotoInfo(driver, photo_id):
    photo_info = {}
    
    print('https://m.facebook.com/photo.php?fbid=' + str(photo_id))
    driver.get('https://m.facebook.com/photo.php?fbid=' + str(photo_id));
    driver.save_screenshot('test.png')
    
    photo_info['url'] = driver.find_element_by_link_text('View Full Size').get_attribute('href')
    
    try:
        likes = driver.find_element_by_css_selector('._1g06')
        likes_text = likes.text
        likes_split = likes_text.split('and ')
        
        if (len(likes_split) > 1):
            subsplit = likes_split[1].split(' others')
            if len(subsplit) > 1:
                num_likes = int(subsplit[0]) + len(likes_split[0].split(','))
            else:
                num_likes = 2
        else:
            try:
                num_likes = int(likes_split[0])
            except ValueError:
                num_likes = 1
        
    except:
        num_likes = 0
    
    photo_info['likes'] = num_likes
    
    abbr = driver.find_element_by_css_selector('._2vja abbr')
    photo_info['timestamp'] = datetime.datetime.fromtimestamp(json.loads(abbr.get_attribute('data-store'))['time'])
    
    photo_info['user'] = driver.find_element_by_css_selector('.actor-link').get_attribute('href')[23:].split('?')[0]
    
    print(photo_info)
    return photo_info

user_ids = getUserIds(driver)

images = set()

for year in ['2016', '2015', '2014', '2013']:
  for user_id in user_ids:
      driver = webdriver.PhantomJS()
                                                  
      for cookie in cookies:
          driver.add_cookie(cookie)
  
      print("Loading page for user '" + user_id + "', year " + year)
      driver.get('https://m.facebook.com/' + user_id + '/year/' + year + '/')
      scrollToBottom(driver)
  
      photos = getPhotoIds(driver)
      images.update(photos)
      
      print("    " + str(len(photos)) + " photos added to " + str(len(images)) + " so far")
  
      driver.quit()

photos_list = list(all_photos)

client = MongoClient('127.0.0.1', 3001)
db = client.meteor

i = 0
finished = []

for photo_id in photos_list[:]:
    print("photo " + str(i) + "/" + str(len(all_photos)))
    
    if (i % 100) == 0:
        driver = webdriver.PhantomJS()

        for cookie in cookies:
            driver.add_cookie(cookie)
        
    photo_info = getPhotoInfo(driver, photo_id)
    
    if (i % 100) == 99:
        driver.quit()

    if photo_info:
        result = db.facebook.insert_one(photo_info)
        finished.append(photo_id)
    i += 1

expired_urls = []
images = list(images)

for i in range(len(images)):
    print(str(i) + "/" + str(len(images)))
    retries = 0
    
    if 'uri' in images[i].keys():
        print('    already done')
    else:
        while retries < 2:
            try:
                response = requests.get(images[i]['url'])
                with Image(file=StringIO(response.content)) as img:
                    img.auto_orient()
                    uris = {}

                    (w,h) = img.size
                    w = int(w)
                    h = int(h)

                    fname = basepath + images[i]['id'] + '.jpg'
                    uris['original'] = fname
                    img.save(filename=fname)

                    images[i]['width'] = w
                    images[i]['height'] = h

                    with img.clone() as img_clone:
                        if w > h:
                            new_width = int(((299.0)/h)*w)
                            img_clone.resize(new_width, 299)
                            img_clone.crop(int((new_width-299.0)/2), 0, width=299, height=299)
                        else:
                            new_height = int(((299.0)/w)*h)
                            img_clone.resize(299, new_height)
                            img_clone.crop(0, int((new_height-299.0)/2), width=299, height=299)

                        fname = basepath + images[i]['id'] + '_299' + '.png'
                        uris['299'] = fname
                        img_clone.save(filename=fname) 

                    with img.clone() as img_clone:
                        if w > h:
                            new_width = int(((256.0)/h)*w)
                            img_clone.resize(new_width, 256)
                            img_clone.crop(int((new_width-256.0)/2), 0, width=256, height=256)
                        else:
                            new_height = int(((256.0)/w)*h)
                            img_clone.resize(256, new_height)
                            img_clone.crop(0, int((new_height-256.0)/2), width=256, height=256)

                        fname = basepath + images[i]['id'] + '_256' + '.png'
                        uris['256'] = fname
                        img_clone.save(filename=fname)

                    images[i]['uri'] = uris

                    db.facebook.update_one({'_id': images[i]['_id']}, {'$set': images[i]})
                    break

            except wand.exceptions.MissingDelegateError:
                print("Missing delegate error -- possible expired URL")
                expired_urls.append(images[i]['id'])
                print("    " + str(len(expired_urls)) + " found expired")
                time.sleep(0.1)
                break

            except requests.exceptions.SSLError:
                print("SSL error, retry " + str(retries))
                time.sleep(0.1)
                retries += 1

            except requests.exceptions.ConnectionError:
                print("Connections error, retry " + str(retries))
                time.sleep(1)
                retries += 1

            except:
                print("Unknown error, retry " + str(retries))
                time.sleep(1)
                retries += 1