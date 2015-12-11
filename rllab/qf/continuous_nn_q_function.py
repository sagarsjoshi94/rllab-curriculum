import lasagne
import lasagne.layers as L
import lasagne.nonlinearities
# Needed for eval to work
import lasagne.init
import theano.tensor as TT
import itertools

from rllab.qf.base import ContinuousQFunction
from rllab.core.lasagne_powered import LasagnePowered
from rllab.core.serializable import Serializable
from rllab.misc import autoargs
from rllab.misc.ext import new_tensor


class ContinuousNNQFunction(ContinuousQFunction, LasagnePowered, Serializable):

    @autoargs.arg('hidden_sizes', type=int, nargs='*',
                  help='list of sizes for the fully-connected hidden layers')
    @autoargs.arg('hidden_nl', type=str, nargs='*',
                  help='list of nonlinearities for the hidden layers')
    @autoargs.arg('hidden_W_init', type=str, nargs='*',
                  help='list of initializers for W for the hidden layers')
    @autoargs.arg('hidden_b_init', type=str, nargs='*',
                  help='list of initializers for b for the hidden layers')
    @autoargs.arg('action_merge_layer', type=int,
                  help='Index for the hidden layer that the action kicks in')
    @autoargs.arg('output_nl', type=str,
                  help='nonlinearity for the output layer')
    @autoargs.arg('output_W_init', type=str,
                  help='initializer for W for the output layer')
    @autoargs.arg('output_b_init', type=str,
                  help='initializer for b for the output layer')
    # pylint: disable=dangerous-default-value
    def __init__(
            self,
            mdp,
            hidden_sizes=[100, 100],
            hidden_nl=['lasagne.nonlinearities.rectify'],
            hidden_W_init=['lasagne.init.HeUniform()'],
            hidden_b_init=['lasagne.init.Constant(0.)'],
            action_merge_layer=-2,
            output_nl='None',
            output_W_init='lasagne.init.Uniform(-3e-3, 3e-3)',
            output_b_init='lasagne.init.Uniform(-3e-3, 3e-3)'):
        # pylint: enable=dangerous-default-value
        obs_var = new_tensor(
            'obs',
            ndim=1+len(mdp.observation_shape),
            dtype=mdp.observation_dtype
        )
        action_var = TT.matrix(
            'action',
            dtype=mdp.action_dtype
        )
        l_obs = L.InputLayer(shape=(None,) + mdp.observation_shape,
                             input_var=obs_var)
        l_action = L.InputLayer(shape=(None, mdp.action_dim),
                                input_var=action_var)

        n_layers = len(hidden_sizes) + 1

        action_merge_layer = \
            (action_merge_layer % n_layers + n_layers) % n_layers

        if len(hidden_nl) == 1:
            hidden_nl *= len(hidden_sizes)
        assert len(hidden_nl) == len(hidden_sizes)

        if len(hidden_W_init) == 1:
            hidden_W_init *= len(hidden_sizes)
        assert len(hidden_W_init) == len(hidden_sizes)

        if len(hidden_b_init) == 1:
            hidden_b_init *= len(hidden_sizes)
        assert len(hidden_b_init) == len(hidden_sizes)

        l_hidden = l_obs

        for idx, size, nl, W_init, b_init in zip(
                itertools.count(), hidden_sizes, hidden_nl,
                hidden_W_init, hidden_b_init):
            if idx == action_merge_layer:
                l_hidden = L.ConcatLayer([l_hidden, l_action])
            l_hidden = L.DenseLayer(
                l_hidden,
                num_units=size,
                W=eval(W_init),
                b=eval(b_init),
                nonlinearity=eval(nl),
                name="h%d" % idx
            )

        if action_merge_layer == n_layers:
            l_hidden = L.ConcatLayer([l_hidden, l_action])

        l_output = L.DenseLayer(
            l_hidden,
            num_units=1,
            W=eval(output_W_init),
            b=eval(output_b_init),
            nonlinearity=eval(output_nl),
            name="output"
        )

        self._output_layer = l_output
        self._obs_layer = l_obs
        self._action_layer = l_action

        super(ContinuousNNQFunction, self).__init__(mdp)
        LasagnePowered.__init__(self, [l_output])
        Serializable.__init__(
            self, mdp=mdp, hidden_sizes=hidden_sizes, hidden_nl=hidden_nl,
            hidden_W_init=hidden_W_init, hidden_b_init=hidden_b_init,
            action_merge_layer=action_merge_layer, output_nl=output_nl,
            output_W_init=output_W_init, output_b_init=output_b_init)

    def get_qval_sym(self, obs_var, action_var):
        qvals = L.get_output(
            self._output_layer,
            {self._obs_layer: obs_var, self._action_layer: action_var}
        )
        return TT.reshape(qvals, (-1,))
