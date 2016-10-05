from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import seaborn
from sklearn import linear_model
import numpy as np
import pickle
import xgboost as xgb
import time

# pull data from Mongodb server and return Numpy arrays
def gather_mongo_data():
    client = MongoClient('127.0.0.1', 3001)
    db = client.meteor
    images = list(db.facebook.find({}))

    df = pd.DataFrame(images)
    df = df.dropna(subset = ['normalized_log_likes'])
    # drop data with missing username
    df = df[df['user'] != 'profile.php']

    # build numpy array from DataFrame
    # there has to be a better way to do this -- I haven't investigated it yet
    likes = np.zeros((len(df), 1))
    pool = np.zeros((len(df), 2048))
    categories = np.zeros((len(df), 1008))
    facedata = np.zeros((len(df), 3))

    j = 0
    for i in df.index:
        likes[j, :] = df['normalized_log_likes'][i]
        pool[j, :] = df['inception_pool'][i]
        categories[j, :] = df['inception_classification'][i]
        facedata[j, :] = [df['faces'][i]['num'], df['faces'][i]['total'], df['faces'][i]['largest']]
        j += 1

    users = set(df['user'])
    users = list(users)
    user_hot = np.zeros((len(df), len(users)))
    user_num = np.zeros(len(df))

    j = 0
    for i in df.index:
        user_index = users.index(df['user'][i])
        user_num[j] = user_index
        user_hot[j, user_index] = 1
        j += 1

    predictors = np.hstack((pool, facedata))
    
    return (predictors, pool, likes, users, user_hot, user_num)

# calculate the n*(n-1)/2 comparisons of elements and measure how many of them are made correctly
def correct_comparisons(y, pred_y):
    comparison_true = (y.reshape(1,-1) - y.reshape(-1, 1)) > 0
    comparison_est = (pred_y.reshape(1,-1) - pred_y.reshape(-1,1)) > 0
        
    return ((np.sum(comparison_true == comparison_est) - len(y))/2, (len(y)**2 - len(y))/2)

# calculate all correct comparisons across test user set
def calculate_correct_comparisons(test_observations, test_users, user_hot, predicted_likes, likes):
    total_correct = 0
    total_comparisons = 0

    test_user_hot = user_hot[test_observations, :]
    
    for i in range(len(test_users)):
        user_test_set = np.any(test_user_hot[:, [test_users[i]]], axis = 1).nonzero()[0]
        
        ypred = np.ravel(predicted_likes[user_test_set])
        y = np.ravel(likes[user_test_set])

        (correct, total) = correct_comparisons(y, ypred)
        total_correct += correct
        total_comparisons += total

    return float(total_correct)/total_comparisons

# split the facebook dataset into training, validation, and test components

def split_datasets(users, user_hot, predictors, likes, seed=0):
    print('Seed value is: ' + str(seed))
    np.random.seed(seed)

    # choose 100 random users to be the test set
    test_users = np.random.choice(len(users), 200)
    test_set = np.any(user_hot[:, test_users], axis = 1).nonzero()[0]
    # choose ~100 random users to be the validation set
    validation_users = [v for v in np.random.choice(len(users), 206) if v not in test_users]
    validation_set = np.any(user_hot[:, validation_users], axis = 1).nonzero()[0]
    
    # training set is everything left
    training_users = [v for v in range(len(users)) if v not in test_users and v not in validation_users]
    training_set = [v for v in range(len(predictors)) if v not in test_set and v not in validation_set]

    print("Training set length: " + str(len(training_set)))
    print("Test set length: " + str(len(test_set)))
    print("Validation set length: " + str(len(validation_set)))
    
    return {"training": {"observations": training_set, "users": training_users, "X": predictors[training_set, :], "y": likes[training_set]}, 
            "validation": {"observations": validation_set, "users": validation_users, "X": predictors[validation_set, :], "y": likes[validation_set]}, 
            "test": {"observations": test_set, "users": test_users, "X": predictors[test_set, :], "y": likes[test_set]}}
            