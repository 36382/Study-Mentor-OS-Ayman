from ayman_os_agent.sheet_store import SheetStore


class FakeWS:
    def __init__(self, values):
        self.values = values
        self.read_calls = 0
        self.cell_updates = []

    def get_all_values(self):
        self.read_calls += 1
        return self.values

    def update_cell(self, row, col, value):
        self.cell_updates.append((row, col, value))


class FakeDoc:
    def __init__(self, ws):
        self.ws = ws

    def worksheet(self, name):
        return self.ws


def make_store(values, ttl=60):
    store = SheetStore(cache_ttl=ttl)
    store.credentials = {"client_email": "sa@test.iam.gserviceaccount.com"}
    store.sheet_id = "fake-sheet-id"
    store._doc = FakeDoc(FakeWS(values))
    store._client = object()
    return store, store._doc.ws


def test_get_records_maps_headers():
    store, ws = make_store([["Code", "Name"], ["CS120", "Networks"], ["", ""]])
    rows = store.get_records("Courses")
    assert rows == [{"Code": "CS120", "Name": "Networks"}]


def test_get_records_cache_respects_ttl():
    store, ws = make_store([["Code"], ["CS120"]], ttl=60)
    store.get_records("Courses")
    store.get_records("Courses")
    assert ws.read_calls == 1  # served from cache

    store2, ws2 = make_store([["Code"], ["CS120"]], ttl=0)
    store2.get_records("Courses")
    store2.get_records("Courses")
    assert ws2.read_calls == 2  # ttl=0 disables caching


def test_is_writable_true_with_doc():
    store, _ = make_store([["Code"]])
    assert store.is_writable() is True
    assert store.mode() == "sheets"


def test_update_first_match_updates_cells_and_invalidates():
    store, ws = make_store([["Task", "Status"], ["واجب", "pending"]])
    ok = store.update_first_match("Tasks", lambda r: r["Task"] == "واجب", {"Status": "done"})
    assert ok
    assert ws.cell_updates == [(2, 2, "done")]
    store.get_records("Tasks")  # cache was invalidated -> fresh read
    assert ws.read_calls == 2  # 1 read inside update_first_match + 1 fresh re-read


def test_update_first_match_no_hit():
    store, ws = make_store([["Task", "Status"], ["واجب", "pending"]])
    assert store.update_first_match("Tasks", lambda r: r["Task"] == "غير موجود", {"Status": "done"}) is False
