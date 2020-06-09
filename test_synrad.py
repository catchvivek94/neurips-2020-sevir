"""
Runs tests for synrad model
"""
import sys
sys.path.append('/home/gridsan/groups/EarthIntelligence/datasets/SEVIR/')
import numpy as np
import tensorflow as tf
import pandas as pd
import os
import h5py
os.environ["HDF5_USE_FILE_LOCKING"]='FALSE'

from tqdm import tqdm
from metrics import probability_of_detection,success_rate
from metrics.histogram import compute_histogram,score_histogram

from readers.synrad_reader import read_data

def ssim(y_true,y_pred,maxVal,**kwargs):
    yt=tf.convert_to_tensor(y_true.astype(np.uint8))
    yp=tf.convert_to_tensor(y_pred.astype(np.uint8))
    #s = tf.image.ssim( yt, yp, max_val=maxVal[0], **kwargs)
    s=tf.image.ssim_multiscale(
              yt, yp, max_val=maxVal[0], filter_size=11, filter_sigma=1.5, k1=0.01, k2=0.03
    )
    #return s
    return tf.reduce_mean(s)

def MAE(y_true,y_pred,dum):
    return tf.reduce_mean(tf.keras.losses.MAE(y_true,y_pred))

def MSE(y_true,y_pred,dum):
    return tf.reduce_mean(tf.keras.losses.MSE(y_true,y_pred))

def run_metric( metric, thres, y_true, y_pred, batch_size):
    result = 0.0
    Ltot = 0.0
    n_batches = int(np.ceil(y_true.shape[0]/batch_size))
    print('Running metric ',metric.__name__,'with thres=',thres)
    for b in tqdm(range(n_batches)):
        start = b*batch_size
        end   = min((b+1)*batch_size,y_true.shape[0])
        L = end-start
        yt = y_true[start:end]
        yp = y_pred[start:end]
        result += metric(yt.astype(np.float32),yp,np.array([thres],dtype=np.float32))*L
        Ltot+=L
    return (result / Ltot).numpy() 

def run_histogram(y_true, y_pred, batch_size=1000,bins=range(255)):
    L = len(bins)-1
    H = np.zeros( (L,L),dtype=np.float64) 
    n_batches = int(np.ceil(y_true.shape[0]/batch_size))
    print('Computing histogram ')
    for b in tqdm(range(n_batches)):
        start = b*batch_size
        end   = min((b+1)*batch_size,y_true.shape[0])
        yt = y_true[start:end]
        yp = y_pred[start:end]
        Hi,rb,cb = compute_histogram(yt,yp,bins)
        H+=Hi
    return H,rb,cb 



def main():
    model_file      = sys.argv[1]
    test_data_file  = sys.argv[2]
    output_csv_file = sys.argv[3]
    print('Loading model')
    model = tf.keras.models.load_model(model_file,compile=False,custom_objects={"tf": tf})
    print('Loading test data')
    x_test,y_test = read_data(test_data_file,0,1)
    print('Applying model to test data')
    y_pred = model.predict([x_test[k] for k in ['ir069','ir107','lght']],batch_size=64)
    if isinstance(y_pred,(list,)):
        y_pred=y_pred[0]
    print('Computing test metrics')
    test_scores = {}
    
    test_scores['ssim'] = run_metric(ssim, [255], y_test['vil'], y_pred, 64)
    test_scores['mse'] = run_metric(MSE, 255, y_test['vil'], y_pred, 64)
    test_scores['mae'] = run_metric(MAE, 255, y_test['vil'], y_pred, 64)
    
    # For other stats, compute histogram over the data
    H,rb,cb=run_histogram(y_test['vil'],y_pred,bins=range(255))
    thresholds = [16,74,133,160,181,219]
    scores = score_histogram(H,rb,cb,thresholds)
    for t in thresholds:
        test_scores['pod%d' % t] = scores[t]['pod']
        test_scores['sucr%d' % t] = 1-scores[t]['far']
        test_scores['csi%d' % t] = scores[t]['csi']
        test_scores['bias%d' % t] = scores[t]['bias']  

    """
    test_scores['pod16'] = run_metric(probability_of_detection, 16, y_test['vil'], y_pred, 64)
    test_scores['pod74'] = run_metric(probability_of_detection, 74, y_test['vil'], y_pred, 64)
    test_scores['pod133'] = run_metric(probability_of_detection, 133, y_test['vil'], y_pred, 64)
    test_scores['pod160'] = run_metric(probability_of_detection, 160, y_test['vil'], y_pred, 64)
    test_scores['pod181'] = run_metric(probability_of_detection, 181, y_test['vil'], y_pred, 64)
    test_scores['pod219'] = run_metric(probability_of_detection, 219, y_test['vil'], y_pred, 64)

    test_scores['sucr16'] = run_metric(success_rate, 16, y_test['vil'], y_pred, 64)
    test_scores['sucr74'] = run_metric(success_rate, 74, y_test['vil'], y_pred, 64)
    test_scores['sucr133'] = run_metric(success_rate, 133, y_test['vil'], y_pred, 64)
    test_scores['sucr160'] = run_metric(success_rate, 160, y_test['vil'], y_pred, 64)
    test_scores['sucr181'] = run_metric(success_rate, 181, y_test['vil'], y_pred, 64)
    test_scores['sucr219'] = run_metric(success_rate, 219, y_test['vil'], y_pred, 64)
    """

    df = pd.DataFrame({k:[v] for k,v in test_scores.items()})
    df.to_csv(output_csv_file)
    
    
    
    
if __name__=='__main__':
    main()

    
    
    