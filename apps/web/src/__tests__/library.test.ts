import { clearCompare, getCollections, getCompare, resetLibraryStore, saveToCollection, toggleCompare } from "@/lib/library";

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  resetLibraryStore();
});

it("saves a paper into a named collection", () => {
  saveToCollection("Reading list", "W1");
  saveToCollection("reading list", "W2");
  const cols = getCollections();
  expect(cols).toHaveLength(1);
  expect(cols[0].paperIds).toEqual(["W1", "W2"]);
  expect(JSON.parse(localStorage.getItem("spe-collections")!)).toHaveLength(1);
});

it("keeps at most two papers in the compare tray", () => {
  toggleCompare("A"); toggleCompare("B"); toggleCompare("C");
  expect(getCompare()).toEqual(["B", "C"]);
  clearCompare();
  expect(getCompare()).toEqual([]);
});
