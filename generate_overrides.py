import json
import perf_regression_check

tagHistory = perf_regression_check.History(json.load(open('where.tags.json')))
overrides = {}
testnames = tagHistory.testnames()
for test in testnames :
     overrides[test] = tagHistory.seriesAtTag(test,
 '3.1.7-Baseline')

tagHistory = perf_regression_check.History(json.load(open('insert.tags.json')))
testnames = [u'Insert.DocValidation.TenInt', u'Insert.DocValidation.OneInt', u'Inserts.PartialIndex.NonFilteredRange', u'Inserts.PartialIndex.FullRange', u'Inserts.PartialIndex.FilteredRange', u'Inserts.PartialIndex.FullRange',  u'Inserts.PartialIndex.FilteredRange', u'Insert.DocValidation.TwentyInt']
for test in testnames :
      overrides[test] = tagHistory.seriesAtTag(test, '3.1.4-Baseline')


tagHistory = perf_regression_check.History(json.load(open('update.tags.json')))
testnames = [u'Update.DocValidation.TwentyNum',  u'Update.DocValidation.TenNum', u'Update.DocValidation.OneNum']
for test in testnames :
      overrides[test] = tagHistory.seriesAtTag(test, '3.1.4-Baseline')

tagHistory = perf_regression_check.History(json.load(open('query.tags.json')))
testnames = [u'Queries.PartialIndex.AllInFilter.FilteredRange', u'Queries.PartialIndex.AllInFilter.FullRange', u'Queries.PartialIndex.FilteredRange', u'Queries.PartialIndex.FullRange', u'Queries.PartialIndex.NonFilteredRange',  u'Queries.Text.FindPhrase', u'Queries.Text.FindPhraseCaseSensitive', u'Queries.Text.FindSingle', u'Queries.Text.FindSingleCaseSensitive', u'Queries.Text.FindThreeWords', u'Queries.Text.FindThreeWordsCaseSensitive']
for test in testnames :
      overrides[test] = tagHistory.seriesAtTag(test, '3.1.4-Baseline')

json.dump(overrides, open('override.json', 'w'), indent=4, separators=(',',':'))
