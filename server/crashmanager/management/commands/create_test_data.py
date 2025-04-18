import json
from base64 import b64encode
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from random import choice, randint
from shutil import rmtree
from subprocess import run
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.management import BaseCommand, CommandError, call_command
from django.utils import timezone
from notifications.models import Notification
from notifications.signals import notify

from covmanager.models import (
    Collection,
    CollectionFile,
    Report,
    ReportConfiguration,
    Repository,
)
from crashmanager.models import (
    OS,
    Bucket,
    BucketWatch,
    Bug,
    BugProvider,
    BugzillaTemplate,
    BugzillaTemplateMode,
    Client,
    CrashEntry,
    Platform,
    Product,
    TestCase,
    Tool,
    User,
)
from FTB.CoverageHelper import calculate_summary_fields, merge_coverage_data
from taskmanager.models import Pool, Task


def create_bucket(shortDescription):
    return Bucket.objects.create(
        frequent=choice((True, False)),
        permanent=choice((True, False)),
        reassign_in_progress=choice((True, False)),
        shortDescription=shortDescription,
        signature='{"symptoms": []}',
    )


def create_bug(provider, external_id):
    return Bug.objects.create(
        externalId=external_id,
        externalType=provider,
    )


def create_crash(tools, oss, platforms, client, bucket=None):
    tool = choice(tools)
    os = choice(oss)
    platform = choice(platforms)
    version = timezone.now().date().isoformat()
    product = Product.objects.get_or_create(name="mozilla-central", version=version)[0]
    testdata = "hello world\n" * randint(1, 20)
    binary = choice((True, False))
    testcase = TestCase(quality=randint(0, 10), isBinary=binary, size=len(testdata))
    testcase.test.save("test.bin" if binary else "test.txt", ContentFile(testdata))
    testcase.save()
    random_time = timedelta(seconds=randint(0, 24 * 3600))

    return CrashEntry.objects.create(
        args="",
        bucket=bucket,
        cachedCrashInfo="",
        client=client,
        crashAddress="",
        crashAddressNumeric=None,
        created=timezone.now() - random_time,
        env="",
        metadata="",
        os=os,
        platform=platform,
        product=product,
        rawCrashData="crashdata",
        rawStderr="stderr",
        rawStdout="stdout",
        shortSignature="Assertion failure: test",
        testcase=testcase,
        tool=tool,
        triagedOnce=False,
    )


def create_notify_bucket_hit(user, n):
    bucket = choice(Bucket.objects.all())
    entry = choice(CrashEntry.objects.filter(bucket=bucket))
    notify.send(
        bucket,
        description=f"Notification {n}",
        level="info",
        recipient=user.user,
        target=entry,
        verb="bucket_hit",
    )


def create_notify_coverage_drop(user, n):
    collection = choice(Collection.objects.all())
    notify.send(
        collection,
        description=f"Notification {n}",
        level="warning",
        recipient=user.user,
        target=collection,
        verb="coverage_drop",
    )


def create_notify_inaccessible(user, n):
    bug = choice(Bug.objects.all())
    notify.send(
        bug,
        description=f"Notification {n}",
        level="info",
        recipient=user.user,
        target=bug,
        verb="inaccessible_bug",
    )


def create_notify_task_failed(user, n):
    task = choice(Task.objects.all())
    notify.send(
        task,
        description=f"Notification {n}",
        level="warning",
        recipient=user.user,
        target=task.pool,
        verb="tasks_failed",
    )


def create_template(mode=BugzillaTemplateMode.Bug, name=""):
    return BugzillaTemplate.objects.create(
        alias="",
        assigned_to="",
        attrs="",
        cc="",
        comment="",
        component="",
        description="",
        keywords="",
        mode=mode,
        name=name,
        op_sys="",
        platform="",
        priority="",
        product="",
        qa_contact="",
        security=False,
        security_group="",
        severity="",
        summary="",
        target_milestone="",
        testcase_filename="",
        version="",
        whiteboard="",
    )


def slug():
    raw = uuid4().bytes
    raw = bytes((raw[0] & 0x7F,)) + raw[1:]
    return b64encode(raw, altchars=b"-_").decode()[:22]


COV_DATA_1 = {
    "children": {
        "a": {
            "children": {
                "test.c": {
                    "coverage": [-1, -1, 1, 1, 1, 1, 0, -1, 1],
                    "name": "test.c",
                }
            },
            "name": "a",
        },
        "b": {
            "children": {
                "testb.c": {
                    "coverage": [-1, -1, 1, 1, 1],
                    "name": "testb.c",
                }
            },
            "name": "b",
        },
        "main.c": {
            "coverage": [-1, -1, -1, -1, -1, -1, -1, 1, 1, 1, -1, 1, -1, 2],
            "name": "main.c",
        },
    },
}
calculate_summary_fields(COV_DATA_1)
COV_DATA_2 = {
    "children": {
        "a": {
            "children": {
                "test.c": {
                    "coverage": [-1, -1, 1, 1, 1, 1, 1, -1, 1],
                    "name": "test.c",
                }
            },
            "name": "a",
        },
        "b": {
            "children": {
                "testb.c": {
                    "coverage": [-1, -1, 1, 1, 1],
                    "name": "testb.c",
                }
            },
            "name": "b",
        },
        "main.c": {
            "coverage": [-1, -1, -1, -1, -1, -1, -1, 2, 1, 1, 1, -1, 1, -1, 2],
            "name": "main.c",
        },
    },
}
calculate_summary_fields(COV_DATA_2)
COV_DATA_3 = {
    "children": {
        "a": {
            "children": {
                "test.c": {
                    "coverage": [-1, -1, 1, 1, 1, 1, 1, -1, 1],
                    "name": "test.c",
                }
            },
            "name": "a",
        },
        "b": {
            "children": {
                "testb.c": {
                    "coverage": [-1, -1, 1, 1, 1],
                    "name": "testb.c",
                }
            },
            "name": "b",
        },
        "main.c": {
            "coverage": [-1, -1, -1, -1, -1, -1, -1, 1, 2, 1, 1, -1, 1, -1, 2],
            "name": "main.c",
        },
    },
}
calculate_summary_fields(COV_DATA_3)


class Command(BaseCommand):
    help = "Create test data for UI testing (requires empty DB)"

    def add_arguments(self, parser):
        parser.add_argument("user")
        parser.add_argument(
            "--delete-all-existing-data-forever",
            action="store_true",
            help="Delete existing data without warning",
        )

    def handle(self, *_args, **options):
        user = User.objects.get(user__username=options["user"])

        if options["delete_all_existing_data_forever"]:
            Bucket.objects.all().delete()
            BucketWatch.objects.all().delete()
            Bug.objects.all().delete()
            BugProvider.objects.all().delete()
            BugzillaTemplate.objects.all().delete()
            Client.objects.all().delete()
            Collection.objects.all().delete()
            CollectionFile.objects.all().delete()
            Notification.objects.all().delete()
            OS.objects.all().delete()
            Platform.objects.all().delete()
            Pool.objects.all().delete()
            Product.objects.all().delete()
            Report.objects.all().delete()
            ReportConfiguration.objects.all().delete()
            Repository.objects.all().delete()
            Task.objects.all().delete()
            Tool.objects.all().delete()
            if Path("/data/repos/cov-example").exists():
                rmtree("/data/repos/cov-example")

        # assert that the DB is empty. we don't want real data mixed with test data
        try:
            assert not Bucket.objects.exists()
            assert not BucketWatch.objects.exists()
            assert not Bug.objects.exists()
            assert not BugProvider.objects.exists()
            assert not BugzillaTemplate.objects.exists()
            assert not Client.objects.exists()
            assert not Collection.objects.exists()
            assert not CollectionFile.objects.exists()
            assert not Notification.objects.exists()
            assert not OS.objects.exists()
            assert not Platform.objects.exists()
            assert not Pool.objects.exists()
            assert not Product.objects.exists()
            assert not Report.objects.exists()
            assert not ReportConfiguration.objects.exists()
            assert not Repository.objects.exists()
            assert not Task.objects.exists()
            assert not Tool.objects.exists()
        except AssertionError:
            raise CommandError(
                "DB contains objects, refusing to create test data"
            ) from None
        if Path("/data/repos/cov-example").exists():
            raise CommandError(
                "test repository exists at /data/repos/cov-example, "
                "remove it to continue"
            ) from None

        # create basic objects to be referenced by others
        tools = [
            Tool.objects.create(name="tool1"),
            Tool.objects.create(name="tool2"),
        ]
        oss = [
            OS.objects.create(name="linux"),
            OS.objects.create(name="windows"),
        ]
        platforms = [
            Platform.objects.create(name="x86_64"),
            Platform.objects.create(name="aarch64"),
        ]
        client = Client.objects.create(name="test-data-creator")

        run(
            [
                "git",
                "clone",
                "https://github.com/MozillaSecurity/cov-example",
            ],
            cwd="/data/repos",
            check=True,
        )
        Path("/data/coverage/coverage").mkdir(parents=True, exist_ok=True)
        Path(
            "/data/coverage/coverage/0f87343595e8908a2989ca7716f71502bf288c72.coverage"
        ).write_text(json.dumps(COV_DATA_1))
        Path(
            "/data/coverage/coverage/58721097e138f17549dc129d7dcc44a0adebe218.coverage"
        ).write_text(json.dumps(COV_DATA_2))
        Path(
            "/data/coverage/coverage/68721097e138f17549dc129d7dcc44a0adebe218.coverage"
        ).write_text(json.dumps(COV_DATA_3))
        merged_covdata = deepcopy(COV_DATA_3)
        merge_coverage_data(merged_covdata, COV_DATA_2)
        Path(
            "/data/coverage/coverage/78721097e138f17549dc129d7dcc44a0adebe218.coverage"
        ).write_text(json.dumps(merged_covdata))
        call_command(
            "setup_repository",
            "cov-example",
            "GITSourceCodeProvider",
            "/data/repos/cov-example",
        )

        repo = Repository.objects.get(name="cov-example")
        initial_cov = Collection.objects.create(
            branch="main",
            client=client,
            coverage=CollectionFile.objects.create(
                file="coverage/0f87343595e8908a2989ca7716f71502bf288c72.coverage"
            ),
            created="2024-11-21T20:48:18Z",
            description="initial",
            repository=repo,
            revision="e46bc9b4ebedcab71f4b977b48a127f4ddbcfc3d",
        )
        Collection.objects.create(
            branch="main",
            client=client,
            coverage=CollectionFile.objects.create(
                file="coverage/58721097e138f17549dc129d7dcc44a0adebe218.coverage"
            ),
            created="2024-11-21T21:48:41Z",
            description="update",
            repository=repo,
            revision="adab95a85e138f792631f19d939dfd1102197acc",
        )
        Collection.objects.create(
            branch="main",
            client=client,
            coverage=CollectionFile.objects.create(
                file="coverage/68721097e138f17549dc129d7dcc44a0adebe218.coverage"
            ),
            created="2024-11-21T22:48:41Z",
            description="update #2",
            repository=repo,
            revision="adab95a85e138f792631f19d939dfd1102197acc",
        )
        agg = Collection.objects.create(
            branch="main",
            client=client,
            coverage=CollectionFile.objects.create(
                file="coverage/78721097e138f17549dc129d7dcc44a0adebe218.coverage"
            ),
            created="2024-11-21T22:48:41Z",
            description="Test aggregate",
            repository=repo,
            revision="adab95a85e138f792631f19d939dfd1102197acc",
        )
        Report.objects.create(
            coverage=initial_cov,
        )
        Report.objects.create(
            coverage=agg,
            public=True,
        )
        rc1 = ReportConfiguration.objects.create(
            description="Test configuration",
            directives="+:*\n-:a/*",
            public=True,
            repository=repo,
        )
        ReportConfiguration.objects.create(
            description="A",
            directives="+:a/*",
            logical_parent=rc1,
            public=True,
            repository=repo,
        )

        # create 250 unbucketed crashes
        for _ in range(250):
            create_crash(tools, oss, platforms, client)

        # create 25 buckets with 10 crashes each
        for idx in range(25):
            b = create_bucket(shortDescription=f"bucket #{idx + 1}")
            for _ in range(10):
                create_crash(tools, oss, platforms, client, bucket=b)

        # create 2 watches
        for _ in range(2):
            bucket = choice(Bucket.objects.all())
            BucketWatch.objects.create(
                bucket=bucket,
                lastCrash=choice(CrashEntry.objects.filter(bucket=bucket)).id,
                user=user,
            )

        # create bug provider
        provider = BugProvider.objects.create(
            classname="BugzillaProvider",
            hostname="bugzilla.allizom.org",
            urlTemplate="https://bugzilla.allizom.org/%s",
        )

        # link 10 buckets to bug provider
        for _ in range(10):
            bucket = choice(Bucket.objects.filter(bug__isnull=True))
            bucket.bug = create_bug(provider, randint(1000, 2000))
            bucket.save()

        # create bugzilla template for bug
        create_template(name="bug template")

        # create bugzilla template for comment
        create_template(name="comment template", mode=BugzillaTemplateMode.Comment)

        # create 10 taskmanager pools
        for n in range(10):
            pool = Pool.objects.create(
                cpu="x86_64",
                cycle_time=timedelta(days=7),
                max_run_time=timedelta(days=1),
                platform="linux",
                pool_id=f"pool{n}",
                pool_name=f"Pool #{n}",
                size=16,
            )

            now = timezone.now()
            # for each pool create 150 tasks
            for tg in range(7):
                group = slug()
                for _ in range(16):
                    Task.objects.create(
                        created=now - timedelta(days=tg),
                        decision_id=group,
                        expires=now + timedelta(days=14 - tg),
                        pool=pool,
                        resolved=now + timedelta(days=1 - tg) if tg else None,
                        run_id=0,
                        started=now - timedelta(days=tg),
                        state=(
                            choice(("completed", "exception", "failed"))
                            if tg
                            else choice(("pending", "running"))
                        ),
                        status_data="hello world",
                        task_id=slug(),
                    )

        # create 30 notifications
        for n in range(30):
            choice(
                (
                    create_notify_bucket_hit,
                    create_notify_coverage_drop,
                    create_notify_inaccessible,
                    create_notify_task_failed,
                )
            )(user, n)
