from __future__ import print_function

import pandas as pd
import numpy as np

import functools
import time
import math


class Puma(object):
    '''Import and run Puma algorithm.'''

    def __init__(self, expression_file, motif_file, s1, s2, t1, t2, ppi_file=None, remove_missing=False):
        '''Load expression, motif and optional ppi data.'''

        # Ale: store s1, s2, t1, t2 and hope lioness uses the same instance of this Puma class
        self.s1 = s1
        self.s2 = s2
        self.t1 = t1
        self.t2 = t2

        # load data from provided files
        self.expression_data = pd.read_table(expression_file, sep='\t', header=None, comment='#')
        if motif_file is not None:
            self.motif_data = pd.read_table(motif_file, sep='\t', header=None, comment='#')
        else:
            self.motif_data = None
        if ppi_file is not None:
            self.ppi_data = pd.read_table(ppi_file, sep='\t', header=None, comment='#')
        else:
            self.ppi_data = None
        # remove missing befor analysis
        if remove_missing and motif_file is not None:
            self.__remove_missing()
        # expression data to matrix
        self.__expression_data_to_matrix()
        # motif data to matrix
        if self.motif_data is not None:
            self.__motif_data_to_matrix()
        # ppi data to matrix
        if self.motif_data is not None:
            self.ppi_matrix = np.identity(self.num_tfs)
            if self.ppi_data is not None:
                self.__ppi_data_to_matrix()
        # Pearson correlation
        self.correlation_matrix = np.corrcoef(self.expression_matrix)
        # run Puma algorithm
        if self.motif_data is not None:
            self.puma_network = self.puma_loop(self.correlation_matrix, self.motif_matrix,
                                                 self.ppi_matrix, step_print=True)
        else:
            self.puma_network = self.correlation_matrix
        # create data frame from results
        if self.motif_data is not None:
            self.__puma_results_data_frame()
        else:
            self.__pearson_results_data_frame()
        return None

    def __remove_missing(self):
        '''Remove genes and tfs not present in all files.'''
        # remove expression not in motif
        self.motif_unique_genes = sorted(list(set(self.motif_data[1])))
        self.expression_data = self.expression_data[self.expression_data[0].isin(self.motif_unique_genes)]
        # remove motif not in expression data
        self.expression_unique_genes = sorted(list(set(self.expression_data[0])))
        self.motif_data = self.motif_data[self.motif_data[1].isin(self.expression_unique_genes)]
        # remove ppi not in motif
        if self.ppi_data is not None:
            self.motif_unique_tfs = sorted(list(set(self.motif_data[0])))
            self.ppi_data = self.ppi_data[self.ppi_data[0].isin(self.motif_unique_tfs)]
            self.ppi_data = self.ppi_data[self.ppi_data[1].isin(self.motif_unique_tfs)]
        return None

    def __expression_data_to_matrix(self):
        '''Create a numpy matrix with the expression data.'''
        # ALE it seems that list is not needed.
        self.gene_names = list(self.expression_data[0])
        self.num_genes = len(self.gene_names)
        # ALE drop the column like this: self.expression_data.drop(self.expression_data.columns[[0]], axis=1)
        self.expression_data = self.expression_data[range(1, len(self.expression_data.columns))]
        self.expression_matrix = np.matrix(self.expression_data.as_matrix())
        return None

    def __motif_data_to_matrix(self):
        '''Create a numpy matrix with motif data.'''

        def match(a, b):
            '''Match function.'''
            if a in b:
                return b.index(a)
            return False

        self.unique_tfs = sorted(list(set(self.motif_data[0])))
        self.num_tfs = len(self.unique_tfs)
        self.motif_matrix = np.zeros((self.num_tfs, self.num_genes))
        idx_tfs = map(functools.partial(match, b=self.unique_tfs), self.motif_data[0])
        idx_genes = map(functools.partial(match, b=self.gene_names), self.motif_data[1])
        idx = np.ravel_multi_index((idx_tfs, idx_genes), self.motif_matrix.shape)
        self.motif_matrix.ravel()[idx] = self.motif_data[2]
        return None

    def __ppi_data_to_matrix(self):
        '''Create a numpy matrix with ppi data.'''

        def match(a, b):
            '''Match function.'''
            if a in b:
                return b.index(a)
            return False

        idx_tf1 = map(functools.partial(match, b=self.unique_tfs), self.ppi_data[0])
        idx_tf2 = map(functools.partial(match, b=self.unique_tfs), self.ppi_data[1])
        idx = np.ravel_multi_index((idx_tf1, idx_tf2), self.ppi_matrix.shape)
        self.ppi_matrix.ravel()[idx] = self.ppi_data[2]
        idx = np.ravel_multi_index((idx_tf2, idx_tf1), self.ppi_matrix.shape)
        self.ppi_matrix.ravel()[idx] = self.ppi_data[2]
        return None

    def puma_loop(self, correlation_matrix, motif_matrix, ppi_matrix, step_print=True):
        '''Run Puma algorithm.'''

        def normalize_network(x):
            mean_col = np.mean(x, axis=0)
            std_col = np.std(x, axis=0)
            mean_row = np.mean(x, axis=1)
            std_row = np.std(x, axis=1)
            norm_col = np.divide((x - np.tile(mean_col, (x.shape[0], 1))), (np.tile(std_col, (x.shape[0], 1))))
            norm_row = np.divide((x - np.tile(mean_row, (x.shape[1], 1)).transpose()),
                                 (np.tile(std_row, (x.shape[1], 1)).transpose()))
            normalized_matrix = norm_col / math.sqrt(2) + norm_row / math.sqrt(2)
            # normalize missing values
            mean_total = np.mean(x)
            std_total = np.std(x)
            norm_total = (x - mean_total) / std_total
            nan_col = np.isnan(norm_col)
            nan_row = np.isnan(norm_row)
            normalized_matrix[nan_col] = norm_row[nan_col] / math.sqrt(2) + norm_total[nan_col] / math.sqrt(2)
            normalized_matrix[nan_row] = norm_col[nan_row] / math.sqrt(2) + norm_total[nan_row] / math.sqrt(2)
            normalized_matrix[nan_col & nan_row] = 2 * norm_col[nan_col & nan_row] / math.sqrt(2)
            return normalized_matrix

        def t_function(x, y):
            '''T function.'''
            a_matrix = np.dot(x, y)
            b_matrix = np.tile(np.sum(np.power(y, 2), axis=0), (x.shape[0], 1))
            c_matrix = np.tile(np.sum(np.power(x, 2), axis=1), (y.shape[1], 1)).transpose()
            a_matrix = np.divide(a_matrix, np.sqrt(b_matrix + c_matrix - np.abs(a_matrix)))
            return a_matrix

        def update_diagonal(diagonal_matrix, num, alpha, step):
            '''Update diagonal.'''
            np.fill_diagonal(diagonal_matrix, np.nan)
            diagonal_std = np.nanstd(diagonal_matrix, 1)
            diagonal_fill = diagonal_std * num * math.exp(2 * alpha * step)
            np.fill_diagonal(diagonal_matrix, diagonal_fill)
            return diagonal_matrix

        puma_loop_time = time.time()
        motif_matrix = normalize_network(motif_matrix)
        ppi_matrix = normalize_network(ppi_matrix)
        TFCoopInit = ppi_matrix.copy()  # ALE
        correlation_matrix = normalize_network(correlation_matrix)
        step = 0
        hamming = 1
        alpha = 0.1
        while hamming > 0.001:
            responsibility = t_function(ppi_matrix, motif_matrix)
            availability = t_function(motif_matrix, correlation_matrix)
            hamming = np.sum(
                np.abs(motif_matrix.flatten() - 0.5 * (responsibility.flatten() + availability.flatten()))) / (
                      self.num_tfs * self.num_genes)
            motif_matrix = (1 - alpha) * motif_matrix + alpha * 0.5 * (responsibility + availability)
            ppi = t_function(motif_matrix, motif_matrix.transpose())
            ppi = update_diagonal(ppi, self.num_tfs, alpha, step)
            ppi_matrix = (1 - alpha) * ppi_matrix + alpha * ppi

            TFCoopDiag = ppi_matrix.diagonal()
            # Ale I think this hassle with sub2ind is not needed at all. can the ppi_matrix/TFCoop change shape? Here they are square..
            # TFCoop(sub2ind([NumTFs, NumTFs], s1, s2)) = TFCoopInit(sub2ind([NumTFs, NumTFs], s1, s2)); % PUMA
            # sub2ind takes square matrix with NumTFs size, then gets the linear index for element (s1,s2). use np.ravel_multi_index
            # np.ravel_multi_index((s1, s2), (self.num_tfs, self.num_tfs))
            ppi_matrix[self.s1][self.s2] = TFCoopInit[self.s1][self.s2]
            ppi_matrix[self.t1][self.t2] = TFCoopInit[self.t1][self.t2]
            np.fill_diagonal(ppi_matrix, TFCoopDiag)

            '''
            #PPI=Tfunction(RegNet, RegNet');
	        #PPI=UpdateDiagonal(PPI, NumTFs, alpha, step);
            #TFCoop=(1-alpha)*TFCoop+alpha*PPI;

            #TFCoop -> ppi_matrix in python
            TFCoopDiag=diag(TFCoop);  #ppi_matrix.diagonal()
	        % PUMA
	        TFCoop(sub2ind([NumTFs, NumTFs],s1,s2))=TFCoopInit(sub2ind([NumTFs, NumTFs],s1,s2)); % PUMA
	        TFCoop(sub2ind([NumTFs, NumTFs],t1,t2))=TFCoopInit(sub2ind([NumTFs, NumTFs],t1,t2)); % PUMA
            TFCoop(1:(size(TFCoop,1)+1):end) =TFCoopDiag; % PUMA

            #CoReg2=Tfunction(RegNet', RegNet);
	        #CoReg2=UpdateDiagonal(CoReg2, NumGenes, alpha, step);
	        #GeneCoReg=(1-alpha)*GeneCoReg+alpha*CoReg2;
            '''

            motif = t_function(motif_matrix.transpose(), motif_matrix)
            motif = update_diagonal(motif, self.num_genes, alpha, step)
            correlation_matrix = (1 - alpha) * correlation_matrix + alpha * motif
            if step_print:
                print('step: {}, hamming: {}'.format(step, hamming))
            step = step + 1
        print('running Puma took: %s seconds' % (time.time() - puma_loop_time))
        return motif_matrix

    def __puma_results_data_frame(self):
        '''Results to data frame.'''
        tfs = np.tile(self.unique_tfs, (len(self.gene_names), 1)).flatten()
        genes = np.tile(self.gene_names, (len(self.unique_tfs), 1)).transpose().flatten()
        motif = self.motif_matrix.transpose().flatten()
        force = self.puma_network.transpose().flatten()
        self.flat_puma_network = force
        self.export_puma_results = pd.DataFrame({'tf': tfs, 'gene': genes, 'motif': motif, 'force': force})
        self.export_puma_results = self.export_puma_results[['tf', 'gene', 'motif', 'force']]
        return None

    def __pearson_results_data_frame(self):
        '''Results to data frame.'''
        genes_1 = np.tile(self.gene_names, (len(self.gene_names), 1)).flatten()
        genes_2 = np.tile(self.gene_names, (len(self.gene_names), 1)).transpose().flatten()
        self.flat_puma_network = self.puma_network.transpose().flatten()
        self.export_puma_results = pd.DataFrame({'tf': genes_1, 'gene': genes_2, 'force': self.flat_puma_network})
        self.export_puma_results = self.export_puma_results[['tf', 'gene', 'force']]
        return None

    def save_puma_results(self, file='puma.pairs'):
        '''Write results to file.'''
        self.export_puma_results.to_csv(file, index=False, header=False, sep="\t")
        return None

    def return_puma_indegree(self):
        '''Return Puma indegree.'''
        subset_indegree = self.export_puma_results[[1, 3]]
        self.puma_indegree = subset_indegree.groupby('gene').sum()
        return self.puma_indegree

    def return_puma_outdegree(self):
        '''Return Puma outdegree.'''
        subset_outdegree = self.export_puma_results[[0, 3]]
        self.puma_outdegree = subset_outdegree.groupby('tf').sum()
        return self.puma_outdegree
