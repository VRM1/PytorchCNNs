'''
This program trains the following self.models with Cifar-10 dataset: https://www.cs.toronto.edu/~kriz/cifar.html

1. Resnet-5
'''
import argparse
import torch
import sys
import torch.nn as nn
from torchvision.datasets import CIFAR10, CIFAR100
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
import torch.optim as optim
import torch.nn as nn
from Model import Lenet5, AlexnetCifar, BAlexnet
from Model import BVGG
from Model import AlexNetB
import pkbar
import os
import numpy as np
from torchsummary import summary
import GPUtil
import torch as th
from Dataset import get_cifar10

torch.manual_seed(33)
np.random.seed(33)
if torch.cuda.is_available():
    # check which gpu is free and assign that gpu
    AVAILABLE_GPU = GPUtil.getAvailable(order='first', limit=1, maxLoad=0.5, \
                                        maxMemory=0.5, includeNan=False, excludeID=[], excludeUUID=[])[0]
    th.cuda.set_device(AVAILABLE_GPU)
    print('Program will be executed on GPU:{}'.format(AVAILABLE_GPU))
    DEVICE = torch.device('cuda:' + str(AVAILABLE_GPU))
else:
    DEVICE = torch.device('cpu')

'''
This program uses CIFAR10 data: https://www.cs.toronto.edu/~kriz/cifar.html for image classification using
several popular self.models based on convolution neural network.
'''
if not os.path.isdir('trained_weights'):
    os.makedirs('trained_weights')


class RunModel:

    def __init__(self, m_name, is_bayesian, d_nam):

        self.epochs = 150
        self.tr_b_sz = 256
        self.tst_b_sz = 10
        self.is_bayesian = is_bayesian

        # path to write trained weights
        self.train_weight_path = 'trained_weights/' + m_name + '-' + d_nam + '-' + str(self.epochs) + \
                                 '-' + str(self.tr_b_sz) + '.pth'

        if d_nam == 'cifar10':
            self.n_classes, self.i_channel, self.i_dim, \
            self.train_d, self.test_d = get_cifar10()

        if d_nam == 'cifar100':
            self.n_classes = 100
            train_d = CIFAR100(
                root='datasets', train=True,
                download=True, transform=self.transform_train)
            test_d = CIFAR100(
                root='datasets', train=False,
                download=True, transform=self.transform_test)

        self.train_len = len(self.train_d)
        self.train_loader = DataLoader(self.train_d, batch_size=self.tr_b_sz, shuffle=True, num_workers=0)

        self.test_loader = DataLoader(self.test_d, batch_size=self.tst_b_sz, shuffle=True, num_workers=0)
        self.test_len = len(self.test_d)
        # beging by doing some pre-processing and scaling of data
        # lenet-5 http://yann.lecun.com/exdb/lenet/
        if m_name == 'lenet5' and not self.is_bayesian:
            self.model = Lenet5(self.n_classes).to(DEVICE)
            t_param = sum(p.numel() for p in self.model.parameters())
            print('Running Mode:{}, #Parameters:{}'.format(m_name, t_param))
            print(summary(self.model, (3, 32, 32)))
        elif m_name == 'alexnet' and not self.is_bayesian:
            self.model = AlexnetCifar(self.n_classes).to(DEVICE)
            t_param = sum(p.numel() for p in self.model.parameters())
            print('Running Mode:{}, #Parameters:{}'.format(m_name, t_param))
            print(summary(self.model, (3, 32, 32)))
        # bayesian alexnet
        elif m_name == 'alexnet' and self.is_bayesian:
            self.model = BAlexnet(self.n_classes).to(DEVICE)
            t_param = sum(p.numel() for p in self.model.parameters())
            print('Running Mode:{}, #Parameters:{}'.format(m_name, t_param))
            # print(summary(self.model, (3,32,32)))
        elif m_name == 'VGG' and self.is_bayesian:
            self.model = BVGG(self.n_classes, self.i_channel, 'VGG11').to(DEVICE)
            self.model.features = torch.nn.DataParallel(self.model.features)
            t_param = sum(p.numel() for p in self.model.parameters())
            print('Running Mode:{}, #Parameters:{}'.format(m_name, t_param))
            # print(summary(self.model, (3,32,32)))

    def Train(self):

        num_of_batches_per_epoch = int(self.train_len / self.tr_b_sz) + 1
        train_loss = 0
        tgt = 10
        criterion = nn.CrossEntropyLoss()
        # optimizer = optim.SGD(self.model.parameters(), lr=0.001, momentum=0.9)
        optimizer = torch.optim.Adam(self.model.parameters())
        for e in range(self.epochs):
            correct = 0
            total = 0
            kbar = pkbar.Kbar(target=num_of_batches_per_epoch,
                              stateful_metrics=['Loss', 'Accuracy'], width=30)
            self.model.train()
            for batch_idx, (X, Y) in enumerate(self.train_loader):

                X, Y = X.to(DEVICE), Y.to(DEVICE)
                optimizer.zero_grad()
                if self.is_bayesian:
                    loss = self.model.sample_elbo(inputs=X,
                                                  labels=Y,
                                                  criterion=criterion,
                                                  sample_nbr=3,
                                                  complexity_cost_weight=1 / 50000)
                else:
                    outputs = self.model(X)
                    loss = criterion(outputs, Y)

                loss.backward()
                # parameter update
                optimizer.step()
                train_loss += loss.item()
                if self.is_bayesian:
                    outputs = self.model(X)

                _, predicted = outputs.max(1)
                total += Y.size(0)
                correct += predicted.eq(Y).sum().item()
                # if (e+1) % 10 == 0:
                kbar.update(batch_idx + 1, values=[("Epoch", e + 1),
                                                   ("Loss", loss.item()), ("Train Accuracy", 100. * correct / total)])
            if (e + 1) % 10 == 0:
                print('', end=" ")

        torch.save(self.model.state_dict(), self.train_weight_path)
        print('Trained Weights are Written to {} file'.format(self.train_weight_path))

    def Test(self):

        num_of_batches_per_epoch = int(self.test_len / self.tst_b_sz) + 1
        self.model.load_state_dict(torch.load(self.train_weight_path))
        correct = 0
        total = 0
        kbar = pkbar.Kbar(target=num_of_batches_per_epoch,
                          stateful_metrics=['Loss', 'Accuracy'], width=11)
        self.model.eval()
        with torch.no_grad():
            for batch_idx, (X, Y) in enumerate(self.test_loader):
                X, Y = X.to(DEVICE), Y.to(DEVICE)
                outputs = self.model(X)
                _, predicted = outputs.max(1)
                total += Y.size(0)
                correct += predicted.eq(Y).sum().item()
                kbar.update(batch_idx + 1, values=[("Accuracy", 100. * correct / total)])
            # print('',end=' ')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CNN self.models that use CIFAR10')
    parser.add_argument('-m', '--model', help='model name 1.lenet5 2.alexnet 3. VGG', default='lenet5')
    parser.add_argument('-ba', '--is_bayesian', help='to use bayesian layer or not', action='store_true')
    parser.add_argument('-d', '--dataset', help='dataset type', default='cifar10')
    args = parser.parse_args()
    run_model = RunModel(args.model, args.is_bayesian, args.dataset)
    run_model.Train()
    run_model.Test()
