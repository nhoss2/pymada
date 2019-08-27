const fetch = require('node-fetch');

if ('AGENT_PORT' in process.env){
    exports.host = "http://localhost:" + process.env['AGENT_PORT'];
} else {
    exports.host = "http://localhost:5001";
}

exports.getTask = async function(){
    const reqUrl = exports.host + '/get_task';
    const task_data = await fetch(reqUrl, {method: 'POST'});
    return await task_data.json();
}

exports.saveResult = async function(result){
    const reqUrl = exports.host + '/save_results';
    const response = await fetch(reqUrl, {
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(result)
    });
    return await response.json();
}

exports.addUrl = async function(url, jsonMetadata=null){
    const reqUrl = exports.host + '/add_url';
    const response = await fetch(reqUrl, {
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({'url': url, 'json_metadata': jsonMetadata})
    });
    return await response.json();
}

exports.logError = async function(errorMsg){
    const reqUrl = exports.host + '/log_error'
    const response = await fetch(reqUrl, {
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({'message': errorMsg})
    })
    return await response.json();
}