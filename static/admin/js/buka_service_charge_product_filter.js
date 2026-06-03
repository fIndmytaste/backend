(function () {
  function vendorProductsUrl() {
    var productSelect = document.getElementById("id_product");
    if (productSelect) {
      var configuredUrl = productSelect.getAttribute("data-vendor-products-url");
      if (configuredUrl) {
        return configuredUrl;
      }
    }

    var marker = "/product/bukaitemservicecharge/";
    var path = window.location.pathname;
    var index = path.indexOf(marker);
    if (index === -1) {
      return null;
    }
    return path.slice(0, index + marker.length) + "vendor-products/";
  }

  function setProductOptions(productSelect, products, selectedProductId) {
    productSelect.innerHTML = "";

    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = products.length
      ? "---------"
      : "No products found for this vendor";
    productSelect.appendChild(placeholder);

    products.forEach(function (product) {
      var option = document.createElement("option");
      option.value = product.id;
      option.textContent = product.name + " - " + product.price;
      if (selectedProductId && product.id === selectedProductId) {
        option.selected = true;
      }
      productSelect.appendChild(option);
    });

    productSelect.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function loadVendorProducts(vendorSelect, productSelect, selectedProductId) {
    var vendorId = vendorSelect.value;
    if (!vendorId) {
      setProductOptions(productSelect, [], "");
      return;
    }

    var endpointUrl = vendorProductsUrl();
    if (!endpointUrl) {
      return;
    }

    productSelect.disabled = true;
    fetch(endpointUrl + "?vendor=" + encodeURIComponent(vendorId), {
      credentials: "same-origin",
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        setProductOptions(productSelect, data.products || [], selectedProductId);
      })
      .finally(function () {
        productSelect.disabled = false;
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var vendorSelect = document.getElementById("id_vendor");
    var productSelect = document.getElementById("id_product");
    if (!vendorSelect || !productSelect) {
      return;
    }

    var currentProductId = productSelect.getAttribute("data-current-product") || "";
    loadVendorProducts(vendorSelect, productSelect, currentProductId);

    vendorSelect.addEventListener("change", function () {
      loadVendorProducts(vendorSelect, productSelect, "");
    });
  });
})();
