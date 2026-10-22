def tags_dir(tmp_path, tags_by_repo):
    d = tmp_path / "tags"
    d.mkdir()
    for repo, tags in tags_by_repo.items():
        (d / repo.replace("/", "__")).with_suffix(".txt").write_text("\n".join(tags) + "\n")
    return d


def test_lists_the_native_repos_to_fetch_tags_for(repo, run):
    code, out, _ = run("native-drift", "--list-repos", "--repo", repo("flutter"))
    assert code == 0
    assert out == "plaxieappier/appier-android\nappier/appier-ios-framework\n"


def test_warns_for_each_pin_behind_the_latest_stable_tag(repo, run, tmp_path):
    d = tags_dir(
        tmp_path,
        {
            "plaxieappier/appier-android": ["8.10.0", "8.11.0", "8.12.0-rc.1"],
            "appier/appier-ios-framework": ["8.11.3", "v8.11.10", "8.9.0"],
        },
    )

    code, out, _ = run("native-drift", "--tags-dir", d, "--repo", repo("flutter"))

    assert code == 0
    assert out == "AppierFramework pins 8.11.3; appier/appier-ios-framework is at 8.11.10\n"


def test_never_fails_even_when_tags_are_missing(repo, run, tmp_path):
    d = tags_dir(tmp_path, {"plaxieappier/appier-android": ["9.0.0"]})

    code, out, _ = run("native-drift", "--tags-dir", d, "--repo", repo("flutter"))

    assert code == 0
    assert "appier-android pins 8.11.0; plaxieappier/appier-android is at 9.0.0" in out
    assert "AppierFramework: no tags found for appier/appier-ios-framework" in out


def test_a_repo_without_native_deps_has_nothing_to_report(repo, run, tmp_path):
    code, out, _ = run("native-drift", "--tags-dir", tmp_path, "--repo", repo("react-native"))
    assert (code, out) == (0, "")
