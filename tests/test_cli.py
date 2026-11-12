"""CLI tests: the three subcommands run end to end."""

from heatrate.cli import main


def test_cli_sweep_small(capsys):
    assert main(["sweep", "--fractions", "1.0,0.5"]) == 0
    out = capsys.readouterr().out
    assert "7856" in out  # design-point heat rate appears in the table


def test_cli_validate(capsys):
    assert main(["validate"]) == 0
    out = capsys.readouterr().out
    assert "THA design" in out
    assert "test measured" in out


def test_cli_export_pypsa(capsys):
    assert main(["export", "--format", "pypsa", "--load", "400"]) == 0
    out = capsys.readouterr().out
    assert "dispatches 400.0 MW" in out


def test_cli_export_pandapower(capsys):
    assert (
        main(["export", "--format", "pandapower", "--cost", "pwl", "--load", "400"])
        == 0
    )
    out = capsys.readouterr().out
    assert "converged=True" in out
