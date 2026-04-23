from suds.client import Client
import time

WSDL_URL = "http://legislatie.just.ro/apiws/FreeWebService.svc?wsdl"


class LegislatieAPIClient:
    def __init__(self):
        print("Connecting to SOAP API...")
        self.client = Client(WSDL_URL)
        self.token = self.client.service.GetToken()
        print(f"Got session token: {self.token[:20]}...")

    def search(self, keyword=None, year=None, doc_type=None, page=0, per_page=20):
        """
        Search the legislation database.

        Parameters:
            keyword  : e.g. "concediu medical", "muncă", "taxe"
            year     : e.g. 2003
            doc_type : e.g. "LEGE", "ORDONANTA", "HOTARARE"
            page     : page number (0-indexed)
            per_page : results per page (max ~50)
        """
        model = self.client.factory.create("SearchModel")
        model.NumarPagina = page
        model.RezultatePagina = per_page

        if keyword: model.SearchText = keyword
        if year: model.SearchAn = str(year)
        if doc_type: model.SearchTipAct = doc_type

        result = self.client.service.Search(model, self.token)

        if not result or not result.Legi:
            return []
        return result.Legi.Lege

    def get_all_ids(self, keyword=None, year=None, doc_type=None, max_pages=10):
        """
        Paginate through all results and collect every law ID.
        """
        all_laws = []
        for page in range(max_pages):
            print(f"  Fetching page {page}...")
            batch = self.search(keyword=keyword, year=year, doc_type=doc_type,
                                page=page, per_page=50)
            if not batch:
                print(f"  No more results at page {page}. Done.")
                break
            all_laws.extend(batch)
            time.sleep(0.5)

        print(f"Found {len(all_laws)} laws total.")
        return all_laws


if __name__ == "__main__":
    client = LegislatieAPIClient()

    laws = client.get_all_ids(keyword="concediu medical", max_pages=3)
    for law in laws[:5]:
        print(f"ID={law.Id}  |  {law.Titlu[:80]}")
