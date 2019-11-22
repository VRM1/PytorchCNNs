'''
This program trains the following self.models with Cifar-10 dataset: https://www.cs.toronto.edu/~kriz/cifar.html

1. Resnet-5
'''
import argparse
import torch
import sys
import torch.nn as nn
from torchvision.datasets import CIFAR10
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
import torch.optim as optim
import torch.nn as nn
from Model import Resnet5
import pkbar
import os
if torch.cuda.is_available():
    DEVICE = torch.device('cuda')
else:
    DEVICE = torch.device('cpu')

'''
This program uses CIFAR10 data: https://www.cs.toronto.edu/~kriz/cifar.html for image classification using
several popular self.models based on convolution neural network.
'''
if not os.path.isdir('trained_weights'):
    os.makedirs('trained_weights')
TWEIGHT_PTH = 'trained_weights/cifar_net.pth'

class RunModel:

    def __init__(self,m_name):

        self.n_classes = 10
        self.epochs = 250
        self.tr_b_sz = 128
        self.tst_b_sz = 10

        self.transform_train = transforms.Compose([transforms.ToTensor(),\
                                        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])
        self.transform_test = transforms.Compose([transforms.ToTensor(),\
                            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])
        train_d = CIFAR10(
                root='datasets', train=True,
                download=True, transform=self.transform_train)
        self.train_len = len(train_d)
        self.train_loader = DataLoader(train_d, batch_size=self.tr_b_sz, shuffle=True, num_workers=4)

        test_d = CIFAR10(
                root='datasets', train=False,
                download=True, transform=self.transform_test)
        self.test_loader = DataLoader(test_d, batch_size=self.tst_b_sz, shuffle=True, num_workers=4)
        self.test_len = len(test_d)
        # beging by doing some pre-processing and scaling of data

        if m_name == 'Restnet5':
            self.model = Resnet5(self.n_classes).to(DEVICE)
            t_param = sum(p.numel() for p in self.model.parameters())
            print('Running Mode:{}, #Parameters:{}'.format(m_name,t_param))
            

    def Train(self):

        num_of_batches_per_epoch = int(self.train_len/self.tr_b_sz)
        train_loss = 0
        tgt = 10
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.SGD(self.model.parameters(), lr=0.001, momentum=0.9)
        for e in range(self.epochs):
            correct = 0
            total = 0
            kbar = pkbar.Kbar(target=num_of_batches_per_epoch, width=11)
            self.model.train()
            for batch_idx, (X, Y) in enumerate(self.train_loader):

                X,Y = X.to(DEVICE), Y.to(DEVICE)
                optimizer.zero_grad()
                outputs = self.model(X)
                loss = criterion(outputs,Y)
                loss.backward()
                # parameter update
                optimizer.step()
                train_loss += loss.item()
                _, predicted = outputs.max(1)
                total += Y.size(0)
                correct += predicted.eq(Y).sum().item()
                if (e+1) % 10 == 0:
                    kbar.update(batch_idx+1, values=[("Epoch", e+1),("Loss", loss.item()), ("Accuracy", 100.*correct/total)])
            if (e+1) % 10 == 0:
                print('',end=" ")

        torch.save(self.model.state_dict(), TWEIGHT_PTH)
        print('Trained Weights are Written to {} file'.format(TWEIGHT_PTH))

    def Test(self):

        num_of_batches_per_epoch = int(self.test_len/self.tst_b_sz)
        self.model.load_state_dict(torch.load(TWEIGHT_PTH))
        correct = 0
        total = 0
        kbar = pkbar.Kbar(target=num_of_batches_per_epoch, width=11)
        self.model.eval()
        with torch.no_grad():
            for batch_idx, (X,Y) in enumerate(self.test_loader):
                X,Y = X.to(DEVICE), Y.to(DEVICE)
                outputs = self.model(X)
                _,predicted = outputs.max(1)
                total += Y.size(0)
                correct += predicted.eq(Y).sum().item()
                kbar.update(batch_idx+1, values=[("Accuracy", 100.*correct/total)])
            # print('',end=' ')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CNN self.models that use CIFAR10')
    parser.add_argument('-m','--model', help='model name', default='Restnet5')
    args = parser.parse_args()
    run_model = RunModel(args.model)
    run_model.Train()
    run_model.Test()
