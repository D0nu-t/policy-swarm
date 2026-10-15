"""Tests for the distance-map maths (classical MDS and Procrustes alignment)."""

import numpy as np

from policyswarm.projection import classical_mds, procrustes_align


def _distances(points):
    return np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)


def test_mds_reproduces_planar_distances_exactly():
    points = np.random.default_rng(0).uniform(-1, 1, size=(25, 2))
    coordinates, fit = classical_mds(_distances(points))
    assert fit > 0.999999
    np.testing.assert_allclose(_distances(coordinates), _distances(points), atol=1e-8)
    np.testing.assert_allclose(coordinates.mean(axis=0), 0, atol=1e-9)


def test_mds_reports_what_a_flat_picture_loses():
    points = np.random.default_rng(1).uniform(-1, 1, size=(40, 4))
    _, fit = classical_mds(_distances(points))
    assert 0.3 < fit < 0.95


def test_mds_handles_degenerate_input():
    coordinates, fit = classical_mds(np.zeros((5, 5)))        # everyone at the same point
    assert coordinates.shape == (5, 2) and np.allclose(coordinates, 0) and fit == 1.0
    assert classical_mds(np.zeros((2, 2)))[0].shape == (2, 2)


def test_procrustes_undoes_rotation_and_reflection():
    reference = np.random.default_rng(2).normal(size=(30, 2))
    reference -= reference.mean(axis=0)
    angle = 1.1
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    mirrored = (reference @ rotation) * np.array([1.0, -1.0])
    np.testing.assert_allclose(procrustes_align(mirrored, reference), reference, atol=1e-9)
    np.testing.assert_allclose(_distances(procrustes_align(mirrored, reference)),
                               _distances(mirrored), atol=1e-9)
