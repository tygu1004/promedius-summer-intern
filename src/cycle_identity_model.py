# -*- coding: utf-8 -*-
"""
Module:    cycle_identity_model.py
Language:  Python3
Date:      2020-06-30 14:16:00
Version:   open.VER 1.0
Developer: LEE GAEUN  (ggelee93@gmail.com) / @author: yeohyeongyu

Copyright (c) Promedius.
All rights reserved.
"""

from __future__ import division
import os
import time
from glob import glob
import tensorflow as tf
import numpy as np
from collections import namedtuple
import cycle_identity_module as md
import inout_util as ut
from PIL import Image

class cycle_identity(object):
    def __init__(self, args):

        ####patients folder name
        #         self.test_patient_no = args.test_patient_no
        #         self.train_patient_no = [d.split('/')[-1] for d in glob(args.dcm_path + '/*') if ('zip' not in d) & (d.split('/')[-1] not in args.test_patient_no)]

        # save directory
        if args.taskID:
            self.taskID = args.taskID
        else:
            self.taskID = ut.TaskID_Generator()
        self.checkpoint_dir = os.path.join(args.checkpoint_dir, self.taskID)
        self.log_dir = os.path.join(args.checkpoint_dir, self.taskID + '_tb')
        print('directory check!!\ncheckpoint : {}\ntensorboard_logs : {}'.format(self.checkpoint_dir, self.log_dir))

        # network options
        OPTIONS = namedtuple('OPTIONS', 'gf_dim glf_dim df_dim \
                              img_channel is_training')
        self.options = OPTIONS._make((args.ngf, args.nglf, args.ndf,
                                      args.img_channel, args.phase == 'train'))

        """
        load images
        """
        print('data load... dicom -> numpy')

        t1 = time.time()
        if args.phase == 'train':
            self.train_image_loader = ut.DCMDataLoader(args.dcm_path,
                                                       image_size=args.whole_size, patch_size=args.patch_size,
                                                       depth=args.img_channel,
                                                       image_max=args.img_vmax, image_min=args.img_vmin,
                                                       batch_size=args.batch_size,
                                                       is_unpair=args.unpair, model=args.model)
            self.test_image_loader = ut.DCMDataLoader(args.dcm_path,
                                                      image_size=args.whole_size, patch_size=args.patch_size,
                                                      depth=args.img_channel,
                                                      image_max=args.img_vmax, image_min=args.img_vmin,
                                                      batch_size=args.batch_size,
                                                      is_unpair=args.unpair, model=args.model)
            self.train_image_loader(args.train_patient_no_A, args.train_patient_no_B)
            self.test_image_loader(args.test_patient_no_A, args.test_patient_no_B)

            print('data load complete !!!, {}\nN_train : {}, N_test : {}'.format(time.time() - t1,
                                                                                 len(
                                                                                     self.train_image_loader.LDCT_image_name),
                                                                                 len(
                                                                                     self.test_image_loader.LDCT_image_name)))
            self.patch_X_set, self.patch_Y_set = self.train_image_loader.get_train_set(args.patch_size)
            self.whole_X_set, self.whole_Y_set = self.test_image_loader.get_test_set()

        else:
            self.test_image_loader = ut.DCMDataLoader(args.dcm_path,
                                                      image_size=args.whole_size, patch_size=args.patch_size,
                                                      depth=args.img_channel,
                                                      image_max=args.img_vmax, image_min=args.img_vmin,
                                                      batch_size=args.batch_size,
                                                      is_unpair=args.unpair, model=args.model)

            self.test_image_loader(args.test_patient_no_A, args.test_patient_no_B)
            print('data load complete !!!, {}, N_test : {}'.format(time.time() - t1,
                                                                   len(self.test_image_loader.LDCT_image_name)))
            self.whole_X_set, self.whole_Y_set = self.test_image_loader.get_test_set()

        """
        build model
        """
        if args.phase == 'train':
            input_shape = (args.patch_size, args.patch_size, args.img_channel)
        else:
            input_shape = (args.whiole_size, args.whiole_size, args.img_channel)
        #### Generator & Discriminator
        # Generator
        self.generator_G = md.generator(input_shape, self.options, name="generatorX2Y")
        self.generator_F = md.generator(input_shape, self.options, name="generatorY2X")
        # Discriminator
        self.discriminator_X = md.discriminator(input_shape, self.options, name="discriminatorX")
        self.discriminator_Y = md.discriminator(input_shape, self.options, name="discriminatorY")

        """
        set check point
        """
        self.ckpt = tf.train.Checkpoint(step=tf.Variable(1),
                                        generator_G=self.generator_G,
                                        generator_F=self.generator_F,
                                        discriminator_X=self.discriminator_X,
                                        discriminator_Y=self.discriminator_Y,
                                        generator_optimizer=tf.keras.optimizers.Adam(learning_rate=args.lr,
                                                                                     beta_1=args.beta1,
                                                                                     beta_2=args.beta2),
                                        discriminator_optimizer=tf.keras.optimizers.Adam(learning_rate=args.lr,
                                                                                         beta_1=args.beta1,
                                                                                         beta_2=args.beta2))
        """
        Summary
        """
        self.writer = tf.summary.create_file_writer(self.log_dir)

        '''
        
        #### image summary
        self.test_G_X = self.generator(self.test_X, self.options, True, name="generatorX2Y")
        self.test_F_Y = self.generator(self.test_Y, self.options, reuse=True, name="generatorY2X")

        self.train_img_summary = tf.concat([self.patch_X, self.patch_Y, self.G_X, self.F_Y], axis=2)
        self.summary_image_train = tf.summary.image('train_patch_image', self.train_img_summary)
        self.test_img_summary = tf.concat([self.test_X, self.test_Y, self.test_G_X, self.test_F_Y], axis=2)
        self.summary_image_test = tf.summary.image('test_whole_image', self.test_img_summary)

        #### psnr summary
        self.summary_psnr_input = tf.summary.scalar("1_psnr", ut.tf_psnr(self.test_X, self.test_Y, 2),
                                                    family='PSNR')  # -1 ~ 1
        self.summary_psnr_result_G = tf.summary.scalar("2_psnr_AtoB", ut.tf_psnr(self.test_Y, self.test_G_X, 2),
                                                       family='PSNR')  # -1 ~ 1
        self.summary_psnr_result_F = tf.summary.scalar("2_psnr_BtoA", ut.tf_psnr(self.test_X, self.test_F_Y, 2),
                                                       family='PSNR')  # -1 ~ 1
        self.summary_psnr = tf.summary.merge(
            [self.summary_psnr_input, self.summary_psnr_result_G, self.summary_psnr_result_F])

        print('--------------------------------------------\n# of parameters : {} '. \
              format(np.sum([np.prod(v.get_shape().as_list()) for v in tf.trainable_variables()])))
        '''

    def train(self, args):
        # @tf.function
        def train_step(patch_X, patch_Y, g_optim, d_optim, step):
            with tf.GradientTape(persistent=True) as tape, self.writer.as_default():
                # forward Generator
                G_X = self.generator_G(patch_X)
                F_GX = self.generator_F(G_X)
                F_Y = self.generator_F(patch_Y)
                G_FY = self.generator_G(F_Y)

                G_Y = self.generator_G(patch_Y)
                F_X = self.generator_F(patch_X)

                # forward Discriminator
                D_GX = self.discriminator_Y(G_X)
                D_FY = self.discriminator_X(F_Y)
                D_Y = self.discriminator_Y(patch_Y)
                D_X = self.discriminator_X(patch_X)

                #### Loss
                # generator loss
                cycle_loss = md.cycle_loss(patch_X, F_GX, patch_Y, G_FY, args.L1_lambda)
                identity_loss = md.identity_loss(patch_X, G_Y, patch_Y, F_X, args.L1_gamma)
                G_loss_X2Y = md.least_square(D_GX, tf.ones_like(D_GX))
                G_loss_Y2X = md.least_square(D_FY, tf.ones_like(D_FY))

                G_loss = G_loss_X2Y + G_loss_Y2X + cycle_loss + identity_loss

                # discriminator loss
                D_loss_patch_Y = md.least_square(D_Y, tf.ones_like(D_Y))
                D_loss_patch_GX = md.least_square(D_GX, tf.zeros_like(D_GX))
                D_loss_patch_X = md.least_square(D_X, tf.ones_like(D_X))
                D_loss_patch_FY = md.least_square(D_FY, tf.zeros_like(D_FY))

                D_loss_Y = (D_loss_patch_Y + D_loss_patch_GX)
                D_loss_X = (D_loss_patch_X + D_loss_patch_FY)
                D_loss = (D_loss_X + D_loss_Y) / 2

                #### loss summary
                # generator

                with tf.name_scope("Generator_loss"):
                    tf.summary.scalar(name="1_G_loss", data=G_loss, step=step)
                    tf.summary.scalar(name="2_cycle_loss", data=cycle_loss, step=step)
                    tf.summary.scalar(name="3_identity_loss", data=identity_loss, step=step)
                    tf.summary.scalar(name="4_G_loss_X2Y", data=G_loss_X2Y, step=step)
                    tf.summary.scalar(name="5_G_loss_Y2X", data=G_loss_Y2X, step=step)

                # discriminator
                with tf.name_scope("Discriminator_loss"):
                    tf.summary.scalar(name="1_D_loss", data=D_loss, step=step)
                    tf.summary.scalar(name="2_D_loss_Y", data=D_loss_patch_Y, step=step)
                    tf.summary.scalar(name="3_D_loss_GX", data=D_loss_patch_GX, step=step)
                    tf.summary.scalar(name="4_D_loss_X", data=D_loss_patch_X, step=step)
                    tf.summary.scalar(name="5_D_loss_FY", data=D_loss_patch_FY, step=step)

            # get gradients values from tape
            generator_g_gradients = tape.gradient(G_loss,
                                                  self.generator_G.trainable_variables)
            generator_f_gradients = tape.gradient(G_loss,
                                                  self.generator_F.trainable_variables)

            discriminator_x_gradients = tape.gradient(D_loss,
                                                      self.discriminator_X.trainable_variables)
            discriminator_y_gradients = tape.gradient(D_loss,
                                                      self.discriminator_Y.trainable_variables)
            # training
            g_optim.apply_gradients(zip(generator_g_gradients,
                                        self.generator_G.trainable_variables))

            g_optim.apply_gradients(zip(generator_f_gradients,
                                        self.generator_F.trainable_variables))

            d_optim.apply_gradients(zip(discriminator_x_gradients,
                                        self.discriminator_X.trainable_variables))

            d_optim.apply_gradients(zip(discriminator_y_gradients,
                                        self.discriminator_Y.trainable_variables))

        # summary test sample image during training
        def check_train_sample(patch_X_batch, patch_Y_batch, step):
            patch_X = tf.expand_dims(patch_X_batch[0], axis=0)
            patch_Y = tf.expand_dims(patch_Y_batch[0], axis=0)
            G_X = self.generator_G(patch_X)
            F_Y = self.generator_F(patch_Y)

            patch_X = self.train_image_loader.rescale_arr(data=patch_X, i_min=tf.math.reduce_min(patch_X), i_max=tf.math.reduce_max(patch_X), o_min=0, o_max=255, out_dtype=tf.uint8)
            patch_Y = self.train_image_loader.rescale_arr(data=patch_Y, i_min=tf.math.reduce_min(patch_Y), i_max=tf.math.reduce_max(patch_Y), o_min=0, o_max=255, out_dtype=tf.uint8)
            G_X = self.test_image_loader.rescale_arr(data=G_X, i_min=tf.math.reduce_min(G_X), i_max=tf.math.reduce_max(G_X), o_min=0, o_max=255, out_dtype=tf.uint8)
            F_Y = self.test_image_loader.rescale_arr(data=F_Y, i_min=tf.math.reduce_min(F_Y), i_max=tf.math.reduce_max(F_Y), o_min=0, o_max=255, out_dtype=tf.uint8)

            with self.writer.as_default():
                with tf.name_scope("check_train_sample"):
                    tf.summary.image(name="patch_X", step=step, data=patch_X, max_outputs=1)
                    tf.summary.image(name="patch_Y", step=step, data=patch_Y, max_outputs=1)
                    tf.summary.image(name="G(patch_X)", step=step, data=G_X, max_outputs=1)
                    tf.summary.image(name="F(patch_Y)", step=step, data=F_Y, max_outputs=1)

        def check_test_sample(step):
            buffer_size = 1000

            sample_whole_X = tf.constant(list(self.whole_X_set.shuffle(buffer_size).take(1).as_numpy_iterator()))
            sample_whole_Y = tf.constant(list(self.whole_Y_set.shuffle(buffer_size).take(1).as_numpy_iterator()))

            G_X = self.generator_G(sample_whole_X)
            F_Y = self.generator_F(sample_whole_Y)

            sample_whole_X = self.train_image_loader.rescale_arr(data=sample_whole_X, i_min=tf.math.reduce_min(sample_whole_X), i_max=tf.math.reduce_max(sample_whole_X), o_min=0, o_max=255, out_dtype=tf.uint8)
            sample_whole_Y = self.train_image_loader.rescale_arr(data=sample_whole_Y, i_min=tf.math.reduce_min(sample_whole_Y), i_max=tf.math.reduce_max(sample_whole_Y), o_min=0, o_max=255, out_dtype=tf.uint8)
            G_X = self.test_image_loader.rescale_arr(data=G_X, i_min=tf.math.reduce_min(G_X), i_max=tf.math.reduce_max(G_X), o_min=0, o_max=255, out_dtype=tf.uint8)
            F_Y = self.test_image_loader.rescale_arr(data=F_Y, i_min=tf.math.reduce_min(F_Y), i_max=tf.math.reduce_max(F_Y), o_min=0, o_max=255, out_dtype=tf.uint8)

            with self.writer.as_default():
                with tf.name_scope("check_test_sample"):
                    tf.summary.image(name="sample_whole_X", step=step, data=sample_whole_X, max_outputs=1)
                    tf.summary.image(name="sample_whole_Y", step=step, data=sample_whole_Y, max_outputs=1)
                    tf.summary.image(name="G(sample_whole_X)", step=step, data=G_X, max_outputs=1)
                    tf.summary.image(name="F(sample_whole_Y)", step=step, data=F_Y, max_outputs=1)

        # #############################
        # pre-trained model load
        # start_step : load SUCCESS -> self.start_step 파일명에 의해 초기화... // failed -> 0

        if args.continue_train:
            is_load, current_step = self.load()
            print(" [*] Load SUCCESS") if is_load else print(" [!] Load failed...")
        else:
            current_step = 0
            print(" [*] Start new train")

        steps_per_epoch = min(len(self.train_image_loader.LDCT_image_name),
                              len(self.train_image_loader.NDCT_image_name)) // args.batch_size

        print('Start point : step : {}'.format(current_step))

        # decay learning rate
        lr_schedule = tf.keras.optimizers.schedules.ExponentialDecay(initial_learning_rate=args.lr,
                                                                     decay_steps=args.decay_step,
                                                                     decay_rate=args.decay_rate, staircase=True)
        d_optim = tf.keras.optimizers.Adam(learning_rate=lr_schedule, beta_1=args.beta1)
        g_optim = tf.keras.optimizers.Adam(learning_rate=lr_schedule, beta_1=args.beta1)

        start_time = time.time()
        for epoch in range(args.end_epoch):

            # for counting steps per epoch
            step_count = 0
            for patch_X, patch_Y in tf.data.Dataset.zip((self.patch_X_set, self.patch_Y_set)):
                train_step(patch_X, patch_Y, g_optim, d_optim, current_step)
                current_step += 1
                step_count += 1
                self.ckpt.step.assign_add(1)
                if current_step % args.print_freq == 0:
                    print(("Epoch: {} {}/{} time: {} ".format(epoch, step_count, steps_per_epoch,
                                                              time.time() - start_time)))
                    # summary training sample image
                    check_train_sample(patch_X, patch_Y, current_step)

                    # check sample image
                    # check_test_sample(current_step)

                if current_step % args.save_freq == 0:
                    self.save(args, current_step)

    # save model
    def save(self, args, step):
        save_file_name = args.model + ".model." + "step_" + str(step)
        self.checkpoint_dir = os.path.join('.', self.checkpoint_dir)

        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)

        path = os.path.abspath(self.ckpt.save(os.path.join(self.checkpoint_dir, save_file_name)))

        print("Save check point : " + path)

    # load model    
    def load(self):
        print(" [*] Reading checkpoint...")
        self.checkpoint_dir = os.path.join('.', self.checkpoint_dir)
        ckpt_state = tf.train.get_checkpoint_state(self.checkpoint_dir)

        if ckpt_state and ckpt_state.model_checkpoint_path:
            self.ckpt.restore(ckpt_state.model_checkpoint_path)
            start_step = int(self.ckpt.step.numpy())
            return True, start_step
        else:
            return False, 0

    def test(self, args):
        if self.load():
            print(" [*] Load SUCCESS")
        else:
            print(" [!] Load failed...")

        ## mk save dir (image & numpy file)    
        npy_save_dir = os.path.join(args.test_npy_save_dir, self.taskID)

        if not os.path.exists(npy_save_dir):
            os.makedirs(npy_save_dir)

        ## test
        for idx in range(len(self.test_image_loader.LDCT_images)):
            test_X = self.test_image_loader.LDCT_images[idx]

            mk_G_X = self.sess.run(self.test_G_X,
                                   feed_dict={self.test_X: test_X.reshape([1] + self.test_X.get_shape().as_list()[1:])})

            save_file_nm_g = 'Gen_from_' + self.test_image_loader.LDCT_image_name[idx]

            np.save(os.path.join(npy_save_dir, save_file_nm_g), mk_G_X)

        for idx in range(len(self.test_image_loader.NDCT_images)):
            test_Y = self.test_image_loader.NDCT_images[idx]

            mk_F_Y = self.sess.run(self.test_F_Y,
                                   feed_dict={self.test_Y: test_Y.reshape([1] + self.test_Y.get_shape().as_list()[1:])})

            save_file_nm_f = 'Gen_from_' + self.test_image_loader.NDCT_image_name[idx]

            np.save(os.path.join(npy_save_dir, save_file_nm_f), mk_F_Y)
