from PIL import Image
import pytesseract
import requests
from lxml import html
import re
import sqlite3

conn = sqlite3.connect('DRT_gov.db')
cursor = conn.cursor()

## Create Table
table = cursor.execute("CREATE TABLE IF NOT EXISTS DRT_DRAT_CASES([Diary no_Year] text, [Case_Type Case_No_Year] text, Date_of_Filing text, Case_Status text, In_the_Court_of text, [Court No] text, Next_Listing_Date text, [Next Listing Purpose] text, Date_of_Disposal text, [Disposal Nature] text, [Petitioner Name] text, Petitioner_Applicant_Address text, [Petitioner Additional Party] text, [Petitioner Advocate Name] text, [Petitioner Additional Advocate] text, Respondent_Name text, Respondent_Defendent_Address text, Respondents_Additional_Party text, [Respondents Advocate Name] text, [Respondents Additional Advocate] text, [Property Type] text, [Detail Of Property] text);")

## Set the tesseract path before calling image_to_string for getting text in captcha image.
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'


class DRT:
	def __init__(self):
		self.url = "https://drt.gov.in/front/page1_advocate.php"
		self.session = requests.Session()
		self.headers = {
			"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36 Edg/99.0.1150.39"
			}
		self.count = 0
	

	def get_captcha(self):
		captcha_url = "https://drt.gov.in/front/captcha.php"

		## SAVE CAPTCHA IMAGE LOCALLY
		file = open('captcha.jpg','wb')
		file.write(self.session.get(captcha_url).content)
		file.close()
		
		## READ TEXT FROM SAVED IMAGE
		captcha_text = pytesseract.image_to_string(Image.open("captcha.jpg")).strip()
		return captcha_text

	def get_results(self, captcha):
		schemaname = "100"		## DRAT/DRAT NAME
		name = "sha"			## PARTY NAME

		print("Schemaname: {}, Party name: {}".format(schemaname, name))
		
		payload = {
				'schemaname': schemaname,
				'name': name,
				'answer': str(captcha),
				'submit11': 'Search'
				}

		## POST SEARCH QUERY
		response = self.session.request("POST", self.url, headers=self.headers, data=payload)
		tree = html.fromstring(response.text)

		## GET SEARCH RESULTS
		case_links = tree.xpath('//a[contains(text(),"MORE DETAIL")]//@href')
		case_links = ["https://drt.gov.in/drtlive/Misdetailreport.php?no=" + link.split("'")[1] for link in case_links]

		return case_links

	def get_case_details(self, link):
		self.count += 1
		print("Getting case %s" % self.count)

		rsp = self.session.get(link)
		response = html.fromstring(self.session.get(link).text)

		final_datalist = []

		## CASE STATUS & CASE LISTING DETAILS
		Case_Keys = [
				"Diary no/Year",
				"Case Type/Case No/Year",
				"Date of Filing",
				"Case Status",
				"In the Court of",
				"Court No",
				"Next Listing Date",
				"Next Listing Purpose",
				"Date of Disposal",
				"Disposal Nature"

		]
		for key in Case_Keys:
			try:
				final_datalist.append(response.xpath('//td[contains(text(),"{}")]//following-sibling::td//text()'.format(key))[0])
			except:
				final_datalist.append("")

		## PETITIONER & RESPONDENTS DETAIL
		pet_resp_detail = response.xpath('//table[@class="table table-bordered"][1]//tr//td/text()')

		party_details = "__".join([i.strip() for i in pet_resp_detail]).replace("\n","").replace("\r","").replace('\xa0',"")
		party_details = party_details.split("__")


		## PETITIONER/APPLICANT DETAIL
		Pet_Name = re.findall(r'Petitioner Name -(.*)Petitioner', party_details[0])
		Pet_Address = re.findall(r'Petitioner/Applicant Address:(.*)', party_details[0])
		Pet_Additional_Party = re.findall(r'Additional Party:(.*)', party_details[1])
		Pet_Advocate_Name = re.findall(r'Advocate Name:(.*)Additional', party_details[2])
		Pet_Additional_Advocate = re.findall(r'Additional Advocate:(.*)', party_details[2])


		## RESPONDENTS/DEFENDENT DETAILS
		Resp_Name = re.findall(r'Respondent Name(.*)Respondent', party_details[3])
		Resp_Address = re.findall(r'Respondent/Defendent Address:(.*)', party_details[3])
		Resp_Additional_Party = re.findall(r'Additional Party:(.*)Advocate Name', party_details[-1])
		Resp_Advocate_Name = re.findall(r'Advocate Name(.*)-Additional', party_details[-1])
		Resp_Additional_Advocate = re.findall(r'Advocate:(.*)', party_details[-1])


		list_party_details = [Pet_Name, Pet_Address, Pet_Additional_Party, Pet_Advocate_Name, Pet_Additional_Advocate, Resp_Name, Resp_Address, Resp_Additional_Party, Resp_Advocate_Name, Resp_Additional_Advocate]

		for info in list_party_details:
			try:
				final_datalist.append(info[0].replace("\xa0","").strip())
			except:
				final_datalist.append("")

		## PROPERTY DETAILS
		propertyy = response.xpath('//table[@class="table table-striped"]//tr')
		property_details = []
		if len(propertyy) > 2:
			for i in range(3, len(propertyy)+1):
				property_details = (response.xpath('//table[@class="table table-striped"]//tr[{}]//td//text()'.format(i)))
				property_details = ([p.strip() for p in  property_details])

		if len(property_details) == 2:
			property_type = property_details[0]
			property_detail = property_details[1]
		else:
			property_type = ""
			property_detail = ""
		final_datalist.append(property_type)
		final_datalist.append(property_detail)

		query = " insert into DRT_DRAT_CASES "+ " values"+str(tuple(final_datalist))
		cursor.execute(query)

if __name__ == '__main__':
	obj = DRT()
	captcha_text = obj.get_captcha()
	data_link = obj.get_results(captcha_text)
	for case_link in data_link:
		obj.get_case_details(case_link)

	conn.commit()
	conn.close()
	print("Saved all cases data into database.")