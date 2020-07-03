# -*- coding: utf-8 -*-
"""
Created on Sat Oct 27 19:52:02 2018

@author: yeohyeongyu
"""
import tensorflow as tf
import numpy as np
from tensorflow.keras import layers

def discriminator(image, options, reuse=False, name='discriminator'):
    def first_layer(input_, out_channels, ks=3, s=1, name='disc_conv_layer'):
        return lrelu(conv2d(input_, out_channels, ks=ks, s=s))

    def conv_layer(input_, out_channels, ks=3, s=1, name='disc_conv_layer'):
        return lrelu(batchnorm(conv2d(input_, out_channels, ks=ks, s=s)))
       
    def last_layer(input_, out_channels, ks=4, s=1, name='disc_conv_layer'):
        return layers.Dense(units=out_channels)(conv2d(input_, out_channels, ks=ks, s=s))

    l1 = first_layer(image, options.df_dim, ks=4, s=2, name='disc_layer1')
    l2 = conv_layer(l1, options.df_dim*2, ks=4, s=2, name='disc_layer2')
    l3 = conv_layer(l2, options.df_dim*4, ks=4, s=2, name='disc_layer3')
    l4 = conv_layer(l3, options.df_dim*8, ks=4, s=1, name='disc_layer4')
    l5 = last_layer(l4, options.img_channel, ks=4, s=1, name='disc_layer5')
    
    return l5



def generator(image, options, reuse=False, name="generator"):
    def conv_layer(input_, out_channels, ks=3, s=1, name='conv_layer'):
        return layers.ReLU()(batchnorm(conv2d(input_, out_channels, ks=ks, s=s)))
    
    def gen_module(input_,  out_channels, ks=3, s=1, name='gen_module'):
        ml1 = conv_layer(input_, out_channels, ks, s, name=name + '_l1')
        ml2 = conv_layer(ml1, out_channels, ks, s, name=name + '_l2')
        ml3 = conv_layer(ml2, out_channels, ks, s, name=name + '_l3')
        concat_l = input_ + ml3
        m_out = layers.ReLU()(concat_l)
        
        return m_out

    l1 = conv_layer(image, options.gf_dim, name='convlayer1') 
    module1 = gen_module(l1, options.gf_dim, name='gen_module1')
    module2 = gen_module(module1, options.gf_dim, name='gen_module2')
    module3 = gen_module(module2, options.gf_dim, name='gen_module3')
    module4 = gen_module(module3, options.gf_dim, name='gen_module4')
    module5 = gen_module(module4, options.gf_dim, name='gen_module5')
    module6 = gen_module(module5, options.gf_dim, name='gen_module6')
    concate_layer = layers.concatenate([l1, module1, \
            module2, module3, module4, module5, module6], axis=3)
    concat_conv_l1 = conv_layer(concate_layer, options.gf_dim, ks=3, s=1, name='concat_convlayer1')
    last_conv_layer = conv_layer(concat_conv_l1, options.glf_dim, ks=3, s=1, name='last_conv_layer')
    output = layers.Add(name='output')([conv2d(last_conv_layer, options.img_channel, ks=3, s=1), image])
    
    return output 


# network components
def lrelu(x, leak=0.2, name="lrelu"):
    return layers.LeakyReLU(alpha=leak)(x)

def batchnorm(input_, name="batch_norm"):
    return layers.BatchNormalization(axis=3, epsilon=1e-5, \
            momentum=0.1,\
            gamma_initializer=tf.random_normal_initializer(1.0, 0.02))(input_, training=True)

def conv2d(batch_input, out_channels, ks=4, s=2, name="cov2d"):
    padded_input = tf.pad(batch_input, [[0, 0], [1, 1], [1, 1], [0, 0]], mode="CONSTANT")
    return layers.Conv2D(out_channels, kernel_size=ks, \
        strides=s, padding="valid", \
        kernel_initializer=tf.random_normal_initializer(0, 0.02))(padded_input)

#### loss
def least_square(A, B):
    return tf.reduce_mean((A - B)**2)
    
def cycle_loss(A, F_GA, B, G_FB, lambda_):
    return lambda_ * (tf.reduce_mean(tf.abs(A - F_GA)) + tf.reduce_mean(tf.abs(B - G_FB)))

def identity_loss(A, G_B, B, F_A, gamma):
    return   gamma * (tf.reduce_mean(tf.abs(G_B - B)) + tf.reduce_mean(tf.abs(F_A - A)))
