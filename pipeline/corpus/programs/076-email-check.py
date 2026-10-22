def is_school_email(address, domain):
    clean = address.strip().lower()
    result = clean.endswith("@" + domain)
    return result


print(is_school_email("Ada@School.org ", "school.org"))
print(is_school_email("sam@home.com", "school.org"))
print(is_school_email("BO@SCHOOL.ORG", "school.org"))
