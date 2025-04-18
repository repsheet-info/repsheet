from repsheet_backend.summarize_members import broken_bill_links

def test_has_broken_bills_links():
    assert broken_bill_links("", set()) == set()
    assert broken_bill_links("[C-11](44-1-C-11)", {"44-1-C-11"}) == set()
    assert broken_bill_links("[C-11](44-1-C-11)", set()) == {"44-1-C-11"}
    assert broken_bill_links("[C-11](44-1-C-11)", {"44-1-C-1"}) == {"44-1-C-11"}
    