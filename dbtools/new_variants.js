// SERVER-35071
function update_task_names(project, storage_engine, suffix, variant_name_from=null, variant_name_to=null) {
    var docs = db.json.find({project_id: project, task_name: {$regex: suffix}});

    var count = 0;
    docs.forEach(function(d) {
        count++;
        if (count % 100 == 0) {
            print(count);
        }
        delete d._id;
        d.task_name = d.task_name.replace(suffix, "");
        if (variant_name_from) {
            d.variant = d.variant.replace(variant_name_from, variant_name_to);
        };
        d.storage_engine = storage_engine;
        db.json.insert(d)
    })
}
